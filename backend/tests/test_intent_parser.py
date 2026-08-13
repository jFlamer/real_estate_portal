"""Intent parsing tests. The LLM route is exercised through validation and
fallback logic only — nothing here touches the network."""

import pytest

from app.services.intent_parser import (
    IntentFilters,
    keyword_intent,
    parse_intent,
    to_search_filters,
)


class TestKeywordFallback:
    """The route used with no API key and after the daily quota is spent."""

    def test_rozpoznaje_wynajem(self):
        assert keyword_intent("looking to rent in Krakow").transaction_type == "rent"

    def test_rozpoznaje_zakup(self):
        assert keyword_intent("I want to buy a flat").transaction_type == "sale"

    def test_nie_zgaduje_typu_transakcji(self):
        assert keyword_intent("nice flat with a balcony").transaction_type is None

    def test_miasto_ze_slownika(self):
        assert keyword_intent("something in Krakow please").city == "Kraków"

    def test_tanie_to_sortowanie_a_nie_prog(self):
        # kluczowa reguła: model nie wie, co dla kogo jest tanie
        intent = keyword_intent("cheap flat")
        assert intent.sort == "price_asc"
        assert intent.price_max is None

    def test_metraz_jako_zakres(self):
        intent = keyword_intent("around 40 m2")
        assert (intent.area_min, intent.area_max) == (30, 50)

    def test_jawny_budzet(self):
        assert keyword_intent("up to 3000 per month").price_max == 3000

    def test_sypialnie_a_nie_pokoje(self):
        intent = keyword_intent("2 bedrooms")
        assert intent.bedrooms_min == 2

    def test_wspollokatorzy_to_dwie_sypialnie(self):
        assert keyword_intent("renting with a flatmate").bedrooms_min == 2

    def test_kuchnia(self):
        assert keyword_intent("open-plan kitchen").open_kitchen is True
        assert keyword_intent("separate kitchen please").open_kitchen is False

    def test_z_czynszem(self):
        assert keyword_intent("under 3500 including fees").include_fees is True

    def test_pusta_fraza_nie_ustawia_nic(self):
        intent = keyword_intent("hello")
        assert intent.model_dump(exclude_none=True) == {}


class TestToSearchFilters:
    def test_domyslnie_sprzedaz(self):
        assert to_search_filters(IntentFilters()).transaction_type == "sale"

    def test_przenosi_pola(self):
        filters = to_search_filters(IntentFilters(transaction_type="rent", bedrooms_min=2, city="Kraków"))
        assert (filters.transaction_type, filters.bedrooms_min, filters.city) == ("rent", 2, "Kraków")

    def test_pola_nieustawione_zostaja_puste(self):
        filters = to_search_filters(IntentFilters(bedrooms_min=1))
        assert filters.price_max is None
        assert filters.area_min is None


class TestIntentSchema:
    """The schema is the whitelist: the model cannot invent a field or a value."""

    def test_odrzuca_nieznane_sortowanie(self):
        with pytest.raises(ValueError):
            IntentFilters(sort="by_vibes")

    def test_odrzuca_nieznany_rynek(self):
        with pytest.raises(ValueError):
            IntentFilters(transaction_type="barter")

    def test_odrzuca_ujemna_cene(self):
        with pytest.raises(ValueError):
            IntentFilters(price_max=-1)

    def test_ignoruje_pole_spoza_kontraktu(self):
        # nieznane klucze po prostu nie istnieją w wyniku
        assert not hasattr(IntentFilters(), "sql")


class StubParser:
    def __init__(self, intent: IntentFilters | None):
        self.intent = intent
        self.calls = 0

    def parse(self, query: str) -> IntentFilters | None:
        self.calls += 1
        return self.intent


class TestParseIntent:
    def test_uzywa_llm_gdy_dostepny(self):
        parser = StubParser(IntentFilters(transaction_type="rent", bedrooms_min=3))
        filters, source = parse_intent("three of us renting together", parser)
        assert source == "llm"
        assert filters.bedrooms_min == 3

    def test_bez_parsera_wchodzi_fallback(self):
        filters, source = parse_intent("cheap flat to rent in Krakow", None)
        assert source == "keywords"
        assert (filters.transaction_type, filters.city, filters.sort) == ("rent", "Kraków", "price_asc")

    def test_awaria_llm_wchodzi_fallback(self):
        filters, source = parse_intent("rent in Krakow", StubParser(None))
        assert source == "keywords"
        assert filters.transaction_type == "rent"

    def test_odwrocone_widelki_sa_odrzucane(self):
        # sprzeczne granice dałyby zero wyników bez wyjaśnienia
        parser = StubParser(IntentFilters(price_min=9000, price_max=3000))
        filters, _ = parse_intent("anything", parser)
        assert filters.price_min is None
        assert filters.price_max == 3000
