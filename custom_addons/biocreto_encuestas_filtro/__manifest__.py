{
    'name': 'BIOCRETO Encuestas - Filtro de fecha',
    'version': '19.0.1.0.0',
    'category': 'Marketing/Surveys',
    'summary': 'Filtro de fecha (rango + atajos) en la pagina de resultados de Survey.',
    'description': 'Modulo aislado que anade un dropdown "Filtro por fecha" al lado del filtro nativo "Todas/Terminadas" en /survey/results/<survey>. Server-side URL-driven (replica el patron nativo) -> el boton imprimir respeta el filtro automaticamente. Filtra por create_date de survey.user_input.',
    'author': 'BIOCRETO',
    'license': 'LGPL-3',
    'depends': [
        'biocreto_encuestas',
    ],
    'data': [
        'views/survey_filtro_templates.xml',
    ],
    'assets': {
        # survey.survey_assets es el bundle de /survey/results/<survey>
        # (recon punto F: manifest del addon survey, lineas 62-78).
        # NO va en web.assets_frontend ni web.assets_backend.
        'survey.survey_assets': [
            'biocreto_encuestas_filtro/static/src/interactions/biocreto_filtro_dates.js',
            'biocreto_encuestas_filtro/static/src/scss/biocreto_filtro_dates.scss',
        ],
    },
    'application': False,
    'installable': True,
    'auto_install': False,
}
