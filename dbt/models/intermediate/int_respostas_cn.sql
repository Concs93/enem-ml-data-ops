{{ config(materialized='view') }}

{{ explode_respostas('CN', 45) }}