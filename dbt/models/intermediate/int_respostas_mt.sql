{{ config(materialized='view') }}

{{ explode_respostas('MT', 45) }}