"""Testy parsowania układu. Nie dotykają sieci — ścieżka LLM jest sprawdzana
na poziomie walidacji i scalania wyników, nie przez wołanie API."""

import pytest

from app.services.layout_parser import (
    Layout,
    heuristic_layout,
    is_plausible,
    kitchen_from_url,
    merge_layout,
    is_daily_quota,
    _to_layouts,
)

BASE_URL = "https://krakow.nieruchomosci-online.pl/mieszkanie,{slug}/123.html"


def layout(bedrooms: int, open_kitchen: bool = True, confidence: str = "high") -> Layout:
    return Layout(index=0, bedrooms=bedrooms, open_kitchen=open_kitchen, confidence=confidence)


class TestKitchenFromUrl:
    @pytest.mark.parametrize(
        "slug, expected",
        [
            ("z-aneksem-kuchennym", True),
            ("z-oddzielna-kuchnia", False),
            ("z-kuchnia-z-oknem", False),
            ("z-kuchnia-w-zabudowie", None),
            ("wysoki-standard", None),
        ],
    )
    def test_czyta_taksonomie_portalu(self, slug, expected):
        assert kitchen_from_url(BASE_URL.format(slug=slug)) is expected

    def test_wiele_czlonow_slugu(self):
        url = "https://krakow.nieruchomosci-online.pl/mieszkanie,m4,z-aneksem-kuchennym/1.html"
        assert kitchen_from_url(url) is True

    def test_brak_url(self):
        assert kitchen_from_url(None) is None
        assert kitchen_from_url("https://example.com/cokolwiek") is None


class TestHeuristicLayout:
    def test_zaklada_ze_jeden_pokoj_to_salon(self):
        out = heuristic_layout("Ładne mieszkanie w centrum.", rooms=3)
        assert out["bedrooms"] == 2
        assert out["layout_confidence"] == "low"

    def test_kawalerka_nie_ma_osobnej_sypialni(self):
        assert heuristic_layout("Kawalerka.", rooms=1)["bedrooms"] == 0

    def test_nie_ufa_liczbie_sypialni_z_opisu(self):
        # „dwie sypialnie" bywa opisem jednego piętra dupleksu albo tylko części
        # pokoi; regex mylił się tam, gdzie proste rooms-1 trafiało
        out = heuristic_layout("Salon oraz dwie sypialnie i gabinet.", rooms=4)
        assert out["bedrooms"] == 3

    def test_kuchnia_z_opisu(self):
        assert heuristic_layout("Salon z aneksem kuchennym.", rooms=2)["open_kitchen"] is True
        assert heuristic_layout("Oddzielna kuchnia z oknem.", rooms=2)["open_kitchen"] is False

    def test_kuchnia_z_url_ma_pierwszenstwo(self):
        # opis mówi o aneksie, ale portal skategoryzował ofertę jako osobną kuchnię
        out = heuristic_layout(
            "Salon z aneksem kuchennym.",
            rooms=2,
            source_url=BASE_URL.format(slug="z-oddzielna-kuchnia"),
        )
        assert out["open_kitchen"] is False

    def test_brak_sygnalow_o_kuchni(self):
        assert heuristic_layout("Mieszkanie do remontu.", rooms=2)["open_kitchen"] is None

    def test_zawsze_niska_pewnosc(self):
        assert heuristic_layout("cokolwiek", rooms=2)["layout_confidence"] == "low"

    def test_nieznana_liczba_pokoi(self):
        assert heuristic_layout("Mieszkanie.", rooms=None)["bedrooms"] is None


class TestIsPlausible:
    def test_sypialni_nie_moze_byc_wiecej_niz_pokoi(self):
        assert is_plausible(layout(5), rooms=3) is False

    def test_poprawna_liczba(self):
        assert is_plausible(layout(2), rooms=3) is True

    def test_mieszkanie_wielopokojowe_ma_sypialnie(self):
        # ogłoszenie inwestycyjne bez opisu układu: model zwrócił 0 przy 7 pokojach
        assert is_plausible(layout(0), rooms=7) is False

    def test_kawalerka_moze_miec_zero(self):
        assert is_plausible(layout(0), rooms=1) is True

    def test_brak_liczby_pokoi_nie_blokuje(self):
        assert is_plausible(layout(9), rooms=None) is True


class TestMergeLayout:
    def test_bierze_wynik_llm(self):
        assert merge_layout(layout(2, open_kitchen=True), None) == {
            "bedrooms": 2,
            "open_kitchen": True,
            "layout_confidence": "high",
        }

    def test_slug_url_wygrywa_z_llm_przy_kuchni(self):
        out = merge_layout(layout(2, open_kitchen=True), BASE_URL.format(slug="z-oddzielna-kuchnia"))
        assert out["open_kitchen"] is False
        assert out["bedrooms"] == 2

    def test_bez_slugu_zostaje_odpowiedz_llm(self):
        out = merge_layout(layout(2, open_kitchen=True), BASE_URL.format(slug="wysoki-standard"))
        assert out["open_kitchen"] is True


class TestToLayouts:
    """Modele bywają twórcze mimo `response_schema` — parser musi to znieść."""

    def test_lista(self):
        text = '[{"index":0,"bedrooms":2,"open_kitchen":true,"confidence":"high"},'\
               ' {"index":1,"bedrooms":1,"open_kitchen":false,"confidence":"low"}]'
        assert sorted(_to_layouts(None, text)) == [0, 1]

    def test_pojedynczy_obiekt_zamiast_listy(self):
        # tak odpowiedział gemini-3.5-flash i wywracał całą partię
        text = '{"index":0,"bedrooms":2,"open_kitchen":true,"confidence":"low"}'
        assert _to_layouts(None, text)[0].bedrooms == 2

    def test_lista_opakowana_w_slownik(self):
        text = '{"items":[{"index":5,"bedrooms":3,"open_kitchen":true,"confidence":"high"}]}'
        assert _to_layouts(None, text)[5].bedrooms == 3

    def test_gotowe_obiekty_z_sdk(self):
        parsed = [Layout(index=7, bedrooms=1, open_kitchen=True, confidence="high")]
        assert _to_layouts(parsed, None)[7].bedrooms == 1


class TestIsDailyQuota:
    @staticmethod
    def _error(quota_id: str) -> Exception:
        exc = Exception()
        exc.details = {"error": {"details": [{"violations": [{"quotaId": quota_id}]}]}}
        return exc

    def test_dobowy(self):
        assert _is_daily_quota(self._error("GenerateRequestsPerDayPerProjectPerModel-FreeTier"))

    def test_minutowy_to_nie_dobowy(self):
        assert not _is_daily_quota(self._error("GenerateRequestsPerMinutePerProject"))

    def test_blad_bez_szczegolow(self):
        assert not _is_daily_quota(Exception("cokolwiek"))


class TestLayoutSchema:
    def test_odrzuca_liczbe_spoza_zakresu(self):
        with pytest.raises(ValueError):
            Layout(index=0, bedrooms=99, open_kitchen=True, confidence="high")

    def test_odrzuca_nieznana_pewnosc(self):
        with pytest.raises(ValueError):
            Layout(index=0, bedrooms=2, open_kitchen=True, confidence="bardzo-wysoka")