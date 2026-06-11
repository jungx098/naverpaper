"""Tests for link classification and normalization in scrape.py."""

import requests

from scrape import Scrape, normalize_link


def test_is_campaign_link_accepts_known_hosts():
    s = Scrape()
    assert s.is_campaign_link("https://campaign2.naver.com/npay/branddraw/")
    assert s.is_campaign_link("https://campaign2-api.naver.com/foo")
    assert s.is_campaign_link("https://ofw.adison.co/u/naverpay/ads/123")


def test_is_campaign_link_rejects_other_hosts():
    s = Scrape()
    assert not s.is_campaign_link("https://www.clien.net/service/board/jirum")
    assert not s.is_campaign_link("https://example.com/")


def test_normalize_link_passthrough():
    url = "https://campaign2.naver.com/npay/branddraw/"
    assert normalize_link(url) == url


def test_normalize_link_strips_prefix_before_scheme():
    assert normalize_link("junk-https://a.naver.com/x") == "https://a.naver.com/x"


def test_normalize_link_truncates_at_crlf():
    assert normalize_link("https://a.naver.com/x\r\ntrailing") == "https://a.naver.com/x"


def test_normalize_link_unwraps_redirect_uri():
    wrapped = "https://gateway.example.com/go?redirect_uri=https://campaign2.naver.com/npay/x"
    assert normalize_link(wrapped) == "https://campaign2.naver.com/npay/x"


def test_get_soup_returns_empty_doc_on_ssl_error(monkeypatch):
    s = Scrape()

    def raise_ssl(*args, **kwargs):
        raise requests.exceptions.SSLError("cert verify failed")

    monkeypatch.setattr(s.session, "get", raise_ssl)

    soup = s._get_soup("https://example.com")

    assert soup.find_all() == []


def test_get_soup_returns_empty_doc_on_request_error(monkeypatch):
    s = Scrape()

    def raise_timeout(*args, **kwargs):
        raise requests.exceptions.Timeout("timed out")

    monkeypatch.setattr(s.session, "get", raise_timeout)

    soup = s._get_soup("https://example.com")

    assert soup.find_all() == []
