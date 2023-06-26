/*** { "revision": "2b9830b4" } ***/

ALTER TABLE qgis_vector_style DROP CONSTRAINT qgis_vector_style_svg_marker_library_id_fkey;
ALTER TABLE qgis_vector_style DROP COLUMN svg_marker_library_id;

