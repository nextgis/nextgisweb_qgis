/*** {
    "revision": "6dc38645", "parents": ["49d19279"],
    "date": "2026-04-14T00:00:00",
    "message": "Add render postprocess settings"
} ***/

ALTER TABLE qgis_raster_style ADD COLUMN postprocess jsonb;
ALTER TABLE qgis_vector_style ADD COLUMN postprocess jsonb;