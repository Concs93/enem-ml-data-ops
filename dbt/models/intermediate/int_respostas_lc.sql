{{ config(materialized='view') }}

{{ explode_respostas_lc() }}