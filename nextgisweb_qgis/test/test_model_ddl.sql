/*** Table: qgis_raster_style ***/

CREATE TABLE qgis_raster_style (
    id integer NOT NULL,
    qgis_format character varying(50) NOT NULL,
    qgis_fileobj_id integer,
    qgis_sld_id integer,
    qgis_scale_range_cache jsonb,
    PRIMARY KEY (id),
    CONSTRAINT qgis_format_check CHECK (CASE qgis_format
        WHEN 'default'
        THEN qgis_sld_id IS NULL AND qgis_fileobj_id IS NULL
        WHEN 'sld'
        THEN qgis_sld_id IS NOT NULL AND qgis_fileobj_id IS NULL
        WHEN 'sld_file'
        THEN qgis_fileobj_id IS NOT NULL AND qgis_sld_id IS NULL
        WHEN 'qml_file'
        THEN qgis_fileobj_id IS NOT NULL AND qgis_sld_id IS NULL
        ELSE FALSE
    END),
    FOREIGN KEY (id) REFERENCES resource (id),
    FOREIGN KEY (qgis_fileobj_id) REFERENCES fileobj (id),
    FOREIGN KEY (qgis_sld_id) REFERENCES sld (id)
);

COMMENT ON TABLE qgis_raster_style IS 'qgis';

/*** Table: qgis_vector_style ***/

CREATE TABLE qgis_vector_style (
    id integer NOT NULL,
    svg_marker_library_id integer,
    qgis_format character varying(50) NOT NULL,
    qgis_fileobj_id integer,
    qgis_sld_id integer,
    qgis_scale_range_cache jsonb,
    PRIMARY KEY (id),
    CONSTRAINT qgis_format_check CHECK (CASE qgis_format
        WHEN 'default'
        THEN qgis_sld_id IS NULL AND qgis_fileobj_id IS NULL
        WHEN 'sld'
        THEN qgis_sld_id IS NOT NULL AND qgis_fileobj_id IS NULL
        WHEN 'sld_file'
        THEN qgis_fileobj_id IS NOT NULL AND qgis_sld_id IS NULL
        WHEN 'qml_file'
        THEN qgis_fileobj_id IS NOT NULL AND qgis_sld_id IS NULL
        ELSE FALSE
    END),
    FOREIGN KEY (id) REFERENCES resource (id),
    FOREIGN KEY (svg_marker_library_id) REFERENCES svg_marker_library (id),
    FOREIGN KEY (qgis_fileobj_id) REFERENCES fileobj (id),
    FOREIGN KEY (qgis_sld_id) REFERENCES sld (id)
);

COMMENT ON TABLE qgis_vector_style IS 'qgis';
