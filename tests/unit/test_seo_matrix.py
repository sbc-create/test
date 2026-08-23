"""REQ-SEO-MATRIX: матрица покрывает все реальные типы страниц."""

from factory.seo import matrix as matrix_mod

REQUIRED_TYPES = {
    "home", "category", "collection", "title", "season", "episode", "article", "news_index",
    "tag", "author", "archive", "paginated_page", "search", "filter_indexable",
    "filter_non_indexable", "legal", "service", "not_found", "gone", "content_unavailable",
}

REQUIRED_FIELDS = {"purpose", "url_template", "http_status", "canonical_rule", "in_sitemap",
                   "title_source", "h1_source", "description_source", "body_source",
                   "structured_data", "required_internal_links", "pagination", "vk_video",
                   "blocked_seo_when"}


def test_matrix_covers_required_page_types():
    ids = {p["id"] for p in matrix_mod.load()["page_types"]}
    missing = REQUIRED_TYPES - ids
    assert not missing, f"в матрице нет типов: {sorted(missing)}"


def test_every_page_type_declares_full_policy():
    for page in matrix_mod.load()["page_types"]:
        missing = REQUIRED_FIELDS - set(page)
        assert not missing, f"{page['id']}: не заполнено {sorted(missing)}"


def test_hard_rules_present_and_block_seo():
    rules = matrix_mod.hard_rules()
    assert len(rules) >= 8
    assert all(rule["blocked_status"] == "BLOCKED_SEO" for rule in rules)


def test_url_policy_is_single_valued():
    policy = matrix_mod.url_policy()
    assert policy["scheme"] == "https"
    assert policy["host_form"] in ("www", "non_www")
    assert isinstance(policy["trailing_slash"], bool)
    assert policy["pagination_template"] in ("/page/{n}/", "?page={n}")
    assert policy["page_one_url"] == "canonical_base"


def test_pagination_policy_forbids_canonical_to_page_one():
    page = matrix_mod.page_type("paginated_page")
    assert page["canonical_rule"] == "self_absolute"
    assert "canonical_points_to_page_one" in page["blocked_seo_when"]
    assert page["out_of_range_behaviour"] == "http_404"
    assert page["page_one_behaviour"] == "redirect_301_to_parent"
    assert page["ordering"] == "deterministic" and page["ordering_tie_breaker"]


def test_search_and_filters_are_not_indexable_by_default():
    assert matrix_mod.page_type("search")["index"] is False
    assert matrix_mod.page_type("filter_non_indexable")["index"] is False
    assert matrix_mod.page_type("filter_indexable")["index_default"] is False


def test_content_unavailable_forbids_video_object():
    page = matrix_mod.page_type("content_unavailable")
    assert "VideoObject" not in page["structured_data"]
    assert "videoobject_emitted" in page["blocked_seo_when"]
    assert "substitute_video_used" in page["blocked_seo_when"]


def test_removed_content_is_not_soft_404():
    assert matrix_mod.page_type("gone")["http_status"] == [410]
    assert "status_200_returned" in matrix_mod.page_type("not_found")["blocked_seo_when"]


def test_matrix_is_marked_unverified_against_blocked_sources():
    data = matrix_mod.load()
    assert data["verified_against_official_docs"] is False, \
        "официальные источники закрыты egress-политикой; матрица обязана нести этот признак"
    assert data["provenance"]
