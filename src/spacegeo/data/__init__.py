"""Getting data from the world into clean, validated DataFrames.

Three independent stages, each depending only on ``spacegeo.common``:

    scraping       download raw files and record provenance
    io             parse raw files into schema-validated UTC DataFrames
    preprocessing  transform clean frames (completeness cuts, declustering, ...)
"""
