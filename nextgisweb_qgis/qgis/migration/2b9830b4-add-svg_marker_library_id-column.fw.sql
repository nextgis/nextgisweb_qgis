/*** {
    "revision": "2b9830b4", "parents": ["00000000"],
    "date": "2020-12-17T00:00:00",
    "message": "Add svg_marker_library_id column"
} ***/

ALTER TABLE qgis_vector_style ADD COLUMN svg_marker_library_id integer;
ALTER TABLE qgis_vector_style  ADD CONSTRAINT qgis_vector_style_svg_marker_library_id_fkey
    FOREIGN KEY (svg_marker_library_id) REFERENCES svg_marker_library (id);