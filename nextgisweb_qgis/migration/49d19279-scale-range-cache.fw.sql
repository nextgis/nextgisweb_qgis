/*** {
    "revision": "49d19279", "parents": ["3f716611"],
    "date": "2025-02-03T07:38:29",
    "message": "Scale range cache"
} ***/

ALTER TABLE qgis_raster_style ADD COLUMN qgis_scale_range_cache jsonb;
ALTER TABLE qgis_vector_style ADD COLUMN qgis_scale_range_cache jsonb;
