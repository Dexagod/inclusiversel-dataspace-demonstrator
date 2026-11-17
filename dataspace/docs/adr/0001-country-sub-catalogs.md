# 1. Country sub-catalogs inside one catalog service

Date: 2026-11-16

We need a Belgian and a French data catalog. Instead of running two catalog services, the one catalog service holds two DCAT sub-catalogs (`belgium`, `france`), linked from the root `dcat:Catalog` with `dcat:catalog` (DCAT 3). A registration names its sub-catalog in the optional `catalog` field; registrations without it stay in the root catalog.

Contract changes in the catalog: new optional `catalog` field on registrations (validated against `CATALOGS` in `catalog/dcat.py`), `catalog` in search summaries, a `catalog` filter on `GET /datasets`, and `GET /catalogs`. The connector keeps using one `CATALOG_URL` and needs no change; `spatial` and the `catalog` field in `catalog_search` results already let an agent tell the two apart.

Existing registrations on the `catalog-data` volume keep no sub-catalog until they are PUT again (`make register` in `../sources`).

Adding a country: one entry in `CATALOGS`.
