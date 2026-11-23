"""Turn registration records into a DCAT / DCAT-AP style RDF graph."""

from rdflib import BNode, Graph, Literal, Namespace, URIRef
from rdflib.namespace import DCAT, DCTERMS, FOAF, RDF, RDFS, XSD

VCARD = Namespace("http://www.w3.org/2006/vcard/ns#")
EU = "http://publications.europa.eu/resource/authority/"
LANGUAGES = {"nl": "NLD", "fr": "FRA", "en": "ENG", "de": "DEU"}
FREQUENCIES = {"CONT", "DAILY", "WEEKLY", "MONTHLY", "QUARTERLY", "ANNUAL", "IRREG", "UNKNOWN"}
OPENAPI = URIRef("https://spec.openapis.org/oas/v3.1.0")
OPENAPI_JSON = URIRef("https://www.iana.org/assignments/media-types/application/vnd.oai.openapi+json")
# Sub-catalogs of the data space, one per country; a registration names its sub-catalog in `catalog`.
CATALOGS = {
    "belgium": {"title": "Accessibility data space catalog: Belgium", "country": "BEL"},
    "france": {"title": "Accessibility data space catalog: France", "country": "FRA"},
    "belgium-mobility": {"title": "Accessibility data space catalog: Belgium, mobility", "country": "BEL"},
    "france-mobility": {"title": "Accessibility data space catalog: France, mobility", "country": "FRA"},
}
RDF_FORMATS = {"turtle": "turtle", "rdf+xml": "xml", "xml": "xml", "ld+json": "json-ld", "n-triples": "nt"}


def extract_dataset(text: str, content_type: str) -> tuple[str, str]:
    """From a publisher's DCAT document, the one dcat:Dataset's URI and its description (with distributions) as Turtle."""
    fmt = next((f for k, f in RDF_FORMATS.items() if k in content_type), "turtle")
    src = Graph().parse(data=text, format=fmt)
    found = list(src.subjects(RDF.type, DCAT.Dataset))
    if len(found) != 1:
        raise ValueError(f"expected exactly one dcat:Dataset in the source DCAT, found {len(found)}")
    ds, sub = found[0], Graph()
    for node in [ds, *src.objects(ds, DCAT.distribution)]:
        for triple in src.cbd(node):
            # Publishers' exports sometimes put plain text where an IRI belongs (e.g. "Ville de Liège"); skip those.
            if not any(isinstance(t, URIRef) and (" " in t or ":" not in t) for t in triple):
                sub.add(triple)
    return str(ds), sub.serialize(format="turtle")


def build_graph(records, base: str) -> Graph:
    g = Graph()
    g.bind("dcat", DCAT)
    g.bind("dct", DCTERMS)
    g.bind("foaf", FOAF)
    g.bind("vcard", VCARD)
    cat = URIRef(f"{base}/catalog")
    g.add((cat, RDF.type, DCAT.Catalog))
    g.add((cat, DCTERMS.title, Literal("Accessibility data space catalog", lang="en")))
    subs = {}
    for cid, c in CATALOGS.items():
        sub = subs[cid] = URIRef(f"{base}/catalogs/{cid}")
        g.add((cat, DCAT.catalog, sub))
        g.add((sub, RDF.type, DCAT.Catalog))
        g.add((sub, DCTERMS.identifier, Literal(cid)))
        g.add((sub, DCTERMS.title, Literal(c["title"], lang="en")))
        g.add((sub, DCTERMS.spatial, URIRef(f"{EU}country/{c['country']}")))

    for d in records:
        ds = URIRef(f"{base}/datasets/{d['id']}")
        svc = URIRef(f"{base}/services/{d['id']}")
        dist = URIRef(f"{base}/datasets/{d['id']}#api")
        home = subs.get(d.get("catalog"), cat)
        g.add((home, DCAT.dataset, ds))
        g.add((home, DCAT.service, svc))

        g.add((ds, RDF.type, DCAT.Dataset))
        g.add((ds, DCTERMS.identifier, Literal(d["id"])))
        g.add((ds, DCTERMS.title, Literal(d["title"])))
        g.add((ds, DCTERMS.description, Literal(d["description"])))
        if d.get("licence"):
            g.add((ds, DCTERMS.license, URIRef(d["licence"])))
        if d.get("licence_note"):
            rights = BNode()
            g.add((ds, DCTERMS.rights, rights))
            g.add((rights, RDF.type, DCTERMS.RightsStatement))
            g.add((rights, RDFS.label, Literal(d["licence_note"])))
        g.add((ds, DCTERMS.modified, Literal(d["modified"], datatype=XSD.dateTime)))
        if d.get("source_dcat"):  # the publisher's own DCAT, copied verbatim
            g.parse(data=d["source_dcat"]["turtle"], format="turtle")
            g.add((ds, DCTERMS.source, URIRef(d["source_dcat"]["uri"])))
        pub = BNode()
        g.add((ds, DCTERMS.publisher, pub))
        g.add((pub, RDF.type, FOAF.Agent))
        g.add((pub, FOAF.name, Literal(d["publisher"]["name"])))
        if d["publisher"].get("url"):
            g.add((pub, FOAF.homepage, URIRef(d["publisher"]["url"])))
        for std in d.get("conforms_to", []):
            s = URIRef(std["url"])
            g.add((ds, DCTERMS.conformsTo, s))
            g.add((s, RDF.type, DCTERMS.Standard))
            g.add((s, DCTERMS.title, Literal(std["title"])))
        if d.get("assessment"):
            prov = BNode()
            g.add((ds, DCTERMS.provenance, prov))
            g.add((prov, RDF.type, DCTERMS.ProvenanceStatement))
            a = d["assessment"]
            g.add((prov, RDFS.label, Literal(f"Collection methods: {', '.join(a['methods'])}. {a['note']}", lang="en")))
        for k in d["keywords"]:
            g.add((ds, DCAT.keyword, Literal(k)))
        for t in d["themes"]:
            g.add((ds, DCAT.theme, URIRef(f"{base}/themes/{t}")))
        for lang in d["languages"]:
            g.add((ds, DCTERMS.language, URIRef(f"{EU}language/{LANGUAGES[lang]}")))
        for s in d["spatial"]:
            loc = BNode()
            g.add((ds, DCTERMS.spatial, loc))
            g.add((loc, RDF.type, DCTERMS.Location))
            g.add((loc, RDFS.label, Literal(s)))
        if d.get("update_frequency"):
            g.add((ds, DCTERMS.accrualPeriodicity, URIRef(f"{EU}frequency/{d['update_frequency']}")))
        if d.get("landing_page"):
            g.add((ds, DCAT.landingPage, URIRef(d["landing_page"])))
        if d.get("contact_email"):
            cp = BNode()
            g.add((ds, DCAT.contactPoint, cp))
            g.add((cp, RDF.type, VCARD.Kind))
            g.add((cp, VCARD.hasEmail, URIRef(f"mailto:{d['contact_email']}")))

        for n, extra in enumerate(d.get("distributions", []), 1):
            x = URIRef(f"{base}/datasets/{d['id']}#dist-{n}")
            g.add((ds, DCAT.distribution, x))
            g.add((x, RDF.type, DCAT.Distribution))
            g.add((x, DCAT.accessURL, URIRef(extra["url"])))
            if extra["media_type"] != "text/html":  # a file, not a page
                g.add((x, DCAT.downloadURL, URIRef(extra["url"])))
            g.add((x, DCAT.mediaType, URIRef(f"https://www.iana.org/assignments/media-types/{extra['media_type']}")))
            if extra.get("title"):
                g.add((x, DCTERMS.title, Literal(extra["title"])))
        g.add((ds, DCAT.distribution, dist))
        g.add((dist, RDF.type, DCAT.Distribution))
        g.add((dist, DCAT.accessURL, URIRef(d["endpoint_url"])))
        g.add((dist, DCAT.accessService, svc))
        if d.get("licence"):
            g.add((dist, DCTERMS.license, URIRef(d["licence"])))

        g.add((svc, RDF.type, DCAT.DataService))
        g.add((svc, DCTERMS.title, Literal(f"{d['title']} API")))
        g.add((svc, DCAT.endpointURL, URIRef(d["endpoint_url"])))
        if d.get("openapi"):  # our resolvable copy, linked to the original
            desc = URIRef(f"{base}/services/{d['id']}/openapi.json")
            g.add((desc, DCTERMS.source, URIRef(d["openapi_url"])))
            g.add((desc, DCTERMS.conformsTo, OPENAPI))
            g.add((desc, DCTERMS.format, OPENAPI_JSON))
        else:  # registered before copies were kept
            desc = URIRef(d["openapi_url"])
        g.add((svc, DCAT.endpointDescription, desc))
        g.add((svc, DCTERMS.conformsTo, OPENAPI))
        g.add((svc, DCAT.servesDataset, ds))
        if d.get("access_note"):
            g.add((svc, DCTERMS.accessRights, Literal(d["access_note"])))
    return g
