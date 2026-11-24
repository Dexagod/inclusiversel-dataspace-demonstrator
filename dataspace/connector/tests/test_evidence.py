from evidence import records

ACCESLIBRE = {"at": ["results"], "name": ["nom"], "url": ["web_url"], "date": ["updated_at"],
              "basis": [{"field": "user_type", "equals": "gestionnaire", "method": "self_declared", "by": "the venue's manager"},
                        {"field": "user_type", "equals": "public", "method": "crowd_sourced", "by": "an Acceslibre contributor"}],
              "default": {"method": "official", "by": "imported from a public dataset"}}


def test_list_answer_gives_link_basis_and_date_per_record():
    body = {"count": 2, "results": [
        {"nom": "Musée A", "web_url": "https://acceslibre.example/app/a", "updated_at": "2024-06-01", "user_type": "gestionnaire"},
        {"nom": "Café B", "web_url": "https://acceslibre.example/app/b", "user_type": "system"}]}
    assert records(body, ACCESLIBRE) == [
        {"name": "Musée A", "url": "https://acceslibre.example/app/a", "date": "2024-06-01",
         "basis": "self_declared", "by": "the venue's manager"},
        {"name": "Café B", "url": "https://acceslibre.example/app/b", "basis": "official", "by": "imported from a public dataset"}]


def test_templates_labels_and_detail_answers():
    spec = {"at": ["results"], "name": ["nom_du_professionnel"], "url": ["https://register.example/{docid}"],
            "basis": [{"field": "droit_d_utilisation_du_label", "equals": "actif", "method": "certified",
                       "by": "Tourisme & Handicap", "label": "Tourisme & Handicap: {handicaps_attribues}"}],
            "default": {"method": "unknown", "note": "label not active"}}
    rec = {"nom_du_professionnel": "Hôtel C", "docid": "th1", "droit_d_utilisation_du_label": "actif",
           "handicaps_attribues": ["MOTEUR", "AUDITIF"]}
    assert records(rec, spec) == [{"name": "Hôtel C", "url": "https://register.example/th1", "basis": "certified",
                                   "by": "Tourisme & Handicap", "label": "Tourisme & Handicap: MOTEUR, AUDITIF"}]
    rec["droit_d_utilisation_du_label"] = "retiré"
    assert records(rec, spec)[0]["note"] == "label not active"


def test_field_missing_from_a_search_hit_means_unknown_not_default():
    spec = {"at": ["places"], "name": ["name"],
            "basis": [{"field": "confirmed_by_inter", "equals": True, "method": "certified", "by": "Inter"}],
            "default": {"method": "crowd_sourced"}}
    hits = records({"places": [{"name": "A", "confirmed_by_inter": True}, {"name": "B", "confirmed_by_inter": False},
                               {"name": "C"}]}, spec)
    assert [h["basis"] for h in hits] == ["certified", "crowd_sourced", "unknown"]


def test_present_rule_and_by_from_a_field():
    spec = {"at": ["rows", "dossiers"], "name": ["name", "reference"], "date": ["updatedAt", "receivedAt"],
            "basis": [{"field": "screenedBy", "present": True, "method": "certified", "by": "on-site screening by {screenedBy}"}],
            "default": {"method": "certified", "by": "on-site screening (ToeVla)"}}
    out = records({"dossiers": [{"reference": "S.1", "receivedAt": "2010-07-28", "screenedBy": "ATO vzw"}]}, spec)
    assert out == [{"name": "S.1", "date": "2010-07-28", "basis": "certified", "by": "on-site screening by ATO vzw"}]
    assert records({"rows": [{"name": "X"}]}, spec)[0]["by"] == "on-site screening (ToeVla)"
    assert records({"unrelated": 1}, spec) == []


def test_website_next_to_proof_and_names_encoded_in_links():
    spec = {"name": ["nom"], "url": ['https://data.example/table/?q="{nom}"'], "website": ["site_web"]}
    rec = {"nom": "Novotel Lille & Co", "site_web": "https://hotel.example/"}
    assert records(rec, spec) == [{"name": "Novotel Lille & Co", "url": "https://data.example/table/?q=\"Novotel%20Lille%20%26%20Co\"",
                                   "website": "https://hotel.example/", "basis": "unknown"}]
