"""AI Generated tests"""

import pytest

from app.services.layout_parser import (
    Layout,
    heuristic_layout,
    is_plausible,
    kitchen_from_url,
    parse_layout,
)

BASE_URL = "https://krakow.nieruchomosci-online.pl/mieszkanie,{slug}/123.html"


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
        out = heuristic_layout("Salon oraz dwie sypialnie i gabinet.", rooms=4)
        assert out["bedrooms"] == 3

    def test_kuchnia_z_opisu(self):
        assert heuristic_layout("Salon z aneksem kuchennym.", rooms=2)["open_kitchen"] is True
        assert heuristic_layout("Oddzielna kuchnia z oknem.", rooms=2)["open_kitchen"] is False

    def test_kuchnia_z_url_ma_pierwszenstwo(self):
        out = heuristic_layout(
            "Salon z aneksem kuchennym.", rooms=2, source_url=BASE_URL.format(slug="z-oddzielna-kuchnia")
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
        assert is_plausible(Layout(bedrooms=5, open_kitchen=True, confidence="high"), rooms=3) is False

    def test_poprawna_liczba(self):
        assert is_plausible(Layout(bedrooms=2, open_kitchen=True, confidence="high"), rooms=3) is True

    def test_brak_liczby_pokoi_nie_blokuje(self):
        assert is_plausible(Layout(bedrooms=9, open_kitchen=True, confidence="high"), rooms=None) is True


class StubParser:
    """Udaje klienta LLM — pozwala przetestować orkiestrację bez sieci."""

    def __init__(self, layout: Layout | None):
        self.layout = layout
        self.calls = 0

    def parse(self, description: str, rooms: int | None) -> Layout | None:
        self.calls += 1
        return self.layout


class TestParseLayout:
    def test_uzywa_wyniku_llm(self):
        parser = StubParser(Layout(bedrooms=2, open_kitchen=True, confidence="high"))
        out = parse_layout("x" * 400, rooms=3, parser=parser)
        assert out == {"bedrooms": 2, "open_kitchen": True, "layout_confidence": "high"}
        assert parser.calls == 1

    def test_slug_url_wygrywa_z_llm_przy_kuchni(self):
        parser = StubParser(Layout(bedrooms=2, open_kitchen=True, confidence="high"))
        out = parse_layout(
            "x" * 400, rooms=3, source_url=BASE_URL.format(slug="z-oddzielna-kuchnia"), parser=parser
        )
        assert out["open_kitchen"] is False
        assert out["bedrooms"] == 2

    def test_niewiarygodna_odpowiedz_schodzi_na_heurystyke(self):
        parser = StubParser(Layout(bedrooms=9, open_kitchen=True, confidence="high"))
        out = parse_layout("x" * 400, rooms=2, parser=parser)
        assert out["bedrooms"] == 1
        assert out["layout_confidence"] == "low"

    def test_awaria_llm_schodzi_na_heurystyke(self):
        out = parse_layout("x" * 400, rooms=3, parser=StubParser(None))
        assert out["bedrooms"] == 2
        assert out["layout_confidence"] == "low"

    def test_krotki_opis_nie_idzie_do_llm(self):
        parser = StubParser(Layout(bedrooms=2, open_kitchen=True, confidence="high"))
        out = parse_layout("Mieszkanie 2-pokojowe.", rooms=2, parser=parser)
        assert parser.calls == 0
        assert out["layout_confidence"] == "low"

    def test_bez_parsera_dziala_heurystyka(self):
        out = parse_layout("Salon z aneksem kuchennym." * 20, rooms=3, parser=None)
        assert out["bedrooms"] == 2
        assert out["open_kitchen"] is True