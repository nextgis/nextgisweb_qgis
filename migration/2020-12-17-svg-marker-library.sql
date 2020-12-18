ALTER TABLE qgis_vector_style ADD COLUMN svg_marker_library_id integer;

ALTER TABLE qgis_vector_style  ADD CONSTRAINT qgis_vector_style_svg_marker_library_id_fkey
    FOREIGN KEY (svg_marker_library_id)
    REFERENCES svg_marker_library (id);