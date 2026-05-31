"""Tests for the SQLite-backed campaign store in scrape.py."""

from scrape import Database


def make_db():
    return Database(":memory:")


def test_update_and_get_campaigns_returns_unvisited():
    db = make_db()
    db.update(["https://a.naver.com/x", "https://b.naver.com/y"])

    campaigns = db.get_campaigns(days=-7, newvisitonly=True)

    assert set(campaigns) == {"https://a.naver.com/x", "https://b.naver.com/y"}


def test_update_is_idempotent_on_duplicate_urls():
    db = make_db()
    db.update(["https://a.naver.com/x"])
    db.update(["https://a.naver.com/x"])

    campaigns = db.get_campaigns(days=-7, newvisitonly=False)

    assert campaigns == ["https://a.naver.com/x"]


def test_stamp_campaign_excludes_visited_when_newvisitonly():
    db = make_db()
    db.update(["https://a.naver.com/x", "https://b.naver.com/y"])

    db.stamp_campaign("https://a.naver.com/x")

    unvisited = db.get_campaigns(days=-7, newvisitonly=True)
    assert unvisited == ["https://b.naver.com/y"]

    all_campaigns = db.get_campaigns(days=-7, newvisitonly=False)
    assert set(all_campaigns) == {"https://a.naver.com/x", "https://b.naver.com/y"}
