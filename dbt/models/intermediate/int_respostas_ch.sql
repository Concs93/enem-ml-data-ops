{{ config(materialized='view') }}

{{ explode_respostas('CH', 45) }}