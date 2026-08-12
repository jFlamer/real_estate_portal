"""Testy normalizacji — każdy przypadek pochodzi z realnych danych z raw.json."""

import pytest

from app.services.normalizer import (
    detect_market,
    detect_price_status,
    extract_city,
    extract_district,
    make_dedup_hash,
    normalize,
    parse_area,
    parse_int,
    parse_price,
)


class TestParsePrice:
    @pytest.mark.parametrize(
        "raw, expected",
        [
            ("755000", 755_000),
            ("1 579 000", 1_579_000),
            ("450 000 zł", 450_000),
            ("", None),
            ("zapytaj o cenę", None),
            (None, None),
        ],
    )
    def test_parsuje_rozne_formaty(self, raw, expected):
        assert parse_price({"offers": [{"price": raw}]}) == expected

    def test_brak_sekcji_offers(self):
        assert parse_price({}) is None


class TestPriceStatus:
    def test_brak_ceny_daje_unknown(self):
        assert detect_price_status(None, "cokolwiek") == "unknown"

    def test_wzmianka_o_negocjacji(self):
        assert detect_price_status(500_000, "Cena do negocjacji.") == "negotiable"

    def test_zwykla_cena(self):
        assert detect_price_status(500_000, "Mieszkanie w centrum.") == "fixed"


class TestParseArea:
    @pytest.mark.parametrize(
        "raw, expected",
        [
            ("37.79", 37.8),
            ("45,5 m²", 45.5),
            ("ok. 45", 45.0),
            ("182.00", 182.0),
            ("", None),
        ],
    )
    def test_parsuje_metraz(self, raw, expected):
        assert parse_area({"floorSize": {"value": raw}}) == expected

    def test_brak_pola(self):
        assert parse_area({}) is None


class TestParseInt:
    @pytest.mark.parametrize(
        "raw, expected", [("2", 2), ("", None), (None, None), ("parter", None), ("-1", -1)]
    )
    def test_liczba_z_pola(self, raw, expected):
        assert parse_int(raw) == expected


class TestExtractCity:
    def test_z_adresu(self):
        record = {"ld_json": {"address": {"addressLocality": "Kraków"}}}
        assert extract_city(record) == "Kraków"

    def test_fallback_na_subdomene(self):
        record = {
            "ld_json": {"address": {"addressLocality": ""}},
            "source_url": "https://czarnochowice.nieruchomosci-online.pl/nowe-mieszkanie,x/1.html",
        }
        assert extract_city(record) == "Czarnochowice"

    def test_fallback_na_tytul_strony(self):
        record = {
            "ld_json": {"address": {}},
            "source_url": "https://nieznane.example.com/x.html",
            "page_title": "Mieszkanie w Krakowie 64,70 m² z rynku pierwotnego",
        }
        assert extract_city(record) == "Kraków"

    def test_brak_jakiegokolwiek_sygnalu(self):
        record = {"ld_json": {}, "source_url": "", "page_title": None}
        assert extract_city(record) is None


class TestExtractDistrict:
    def test_po_ostatnim_przecinku(self):
        title = "Sprzedam mieszkanie w bloku mieszkalnym 40 m² Kraków, Prądnik Biały"
        assert extract_district(title, "Kraków") == "Prądnik Biały"

    def test_przecinek_dziesietny_nie_jest_separatorem(self):
        # pułapka: „64,70" to przecinek w liczbie, nie granica dzielnicy
        title = "Mieszkanie w Krakowie 64,70 m² z rynku pierwotnego"
        assert extract_district(title, "Kraków") is None

    def test_ucina_doklejone_miasto(self):
        assert extract_district("Mieszkanie 2pok, Ruczaj Kraków", "Kraków") == "Ruczaj"

    def test_oficjalna_nazwa_dzielnicy(self):
        title = "Mieszkanie 50 m², Dzielnica XII Bieżanów-Prokocim (Bieżanów-Prokocim)"
        assert extract_district(title, "Kraków") == "Bieżanów-Prokocim"

    def test_oficjalna_nazwa_bez_nawiasu(self):
        assert extract_district("Mieszkanie 50 m², Dzielnica VI Bronowice", "Kraków") == "Bronowice"

    def test_samo_miasto_to_nie_dzielnica(self):
        assert extract_district("Mieszkanie 50 m² ul. Długa, Kraków", "Kraków") is None

    def test_odrzuca_smieci_z_tytulu(self):
        assert extract_district("Mieszkanie 32 m² | noho Kraków | Ogród", "Kraków") is None
        assert extract_district("Zamieszkaj w pradze, nowe Kraków", "Kraków") is None

    def test_brak_przecinka(self):
        assert extract_district("Mieszkanie na sprzedaż", "Kraków") is None

    def test_brak_tytulu(self):
        assert extract_district(None, "Kraków") is None


class TestDetectMarket:
    def test_pierwotny_po_url(self):
        record = {"source_url": "https://krakow.nieruchomosci-online.pl/nowe-mieszkanie,x/1.html"}
        assert detect_market(record) == "primary"

    def test_pierwotny_po_tytule(self):
        record = {"source_url": "https://x.pl/a/1.html", "page_title": "Mieszkanie z rynku pierwotnego"}
        assert detect_market(record) == "primary"

    def test_wtorny_gdy_jest_adres(self):
        record = {
            "source_url": "https://krakow.nieruchomosci-online.pl/mieszkanie,x/1.html",
            "ld_json": {"address": {"streetAddress": "Stanisława Lema"}},
        }
        assert detect_market(record) == "secondary"

    def test_nieznany_gdy_brak_sygnalow(self):
        record = {"source_url": "https://krakow.nieruchomosci-online.pl/mieszkanie,x/1.html"}
        assert detect_market(record) == "unknown"


class TestDedupHash:
    def test_te_same_dane_daja_ten_sam_hash(self):
        a = make_dedup_hash("sale", "Kraków", "ul. Długa 5", 45.5, 2, 500_000)
        b = make_dedup_hash("sale", "Kraków", "ul. Długa 5", 45.5, 2, 500_000)
        assert a == b

    def test_ignoruje_wielkosc_liter_i_spacje(self):
        a = make_dedup_hash("sale", "Kraków", "ul. Długa 5", 45.5, 2, 500_000)
        b = make_dedup_hash("sale", "kraków", "  ul.  Długa 5 ", 45.5, 2, 500_000)
        assert a == b

    def test_inna_cena_daje_inny_hash(self):
        a = make_dedup_hash("sale", "Kraków", "ul. Długa 5", 45.5, 2, 500_000)
        b = make_dedup_hash("sale", "Kraków", "ul. Długa 5", 45.5, 2, 600_000)
        assert a != b

    def test_sprzedaz_i_wynajem_to_osobne_oferty(self):
        a = make_dedup_hash("sale", "Kraków", "ul. Długa 5", 45.5, 2, 500_000)
        b = make_dedup_hash("rent", "Kraków", "ul. Długa 5", 45.5, 2, 500_000)
        assert a != b


class TestNormalize:
    @pytest.fixture
    def record(self):
        return {
            "source": "nieruchomosci-online.pl",
            "source_url": "https://krakow.nieruchomosci-online.pl/mieszkanie,na-sprzedaz/1.html",
            "title": "Mieszkanie, ul. Lema",
            "page_title": "Sprzedam mieszkanie 37,79 m² Kraków, Grzegórzki",
            "description": "Dwupokojowe mieszkanie z widokiem na zieleń.",
            "ld_json": {
                "@type": "Apartment",
                "numberOfRooms": 2,
                "floorSize": {"value": "37.79"},
                "address": {"streetAddress": "Stanisława Lema", "addressLocality": "Kraków"},
                "offers": [{"price": "755000"}],
                "additionalProperty": [{"name": "Floor level", "value": "2"}],
            },
        }

    def test_mapuje_wszystkie_pola(self, record):
        row = normalize(record)
        assert row["price"] == 755_000
        assert row["price_status"] == "fixed"
        assert row["area"] == 37.8
        assert row["rooms"] == 2
        assert row["floor"] == 2
        assert row["city"] == "Kraków"
        assert row["district"] == "Grzegórzki"
        assert row["market"] == "secondary"
        assert len(row["dedup_hash"]) == 64

    def test_stare_oferty_bez_pola_to_sprzedaz(self, record):
        assert normalize(record)["transaction_type"] == "sale"

    def test_czyta_typ_transakcji(self, record):
        assert normalize(record | {"transaction_type": "rent"})["transaction_type"] == "rent"

    def test_zachowuje_surowy_rekord(self, record):
        assert normalize(record)["raw_json"] == record

    def test_brakujace_pola_nie_wywracaja_normalizacji(self):
        row = normalize({"source_url": "https://x.pl/a/1.html", "ld_json": {}})
        assert row["price"] is None
        assert row["price_status"] == "unknown"
        assert row["area"] is None
        assert row["rooms"] is None
        assert row["district"] is None