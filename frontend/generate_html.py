from io import BytesIO

def generate_html(summary_text: str, title: str = "Résumé généré par Paper Scanner IA", source: str = None) -> BytesIO:
    html = f"""
    <!DOCTYPE html>
    <html lang="fr">
    <head>
        <meta charset="UTF-8">
        <title>{title}</title>
        <style>
            body {{
                font-family: 'Segoe UI', Arial, sans-serif;
                background: #fafaff;
                color: #222;
                max-width: 800px;
                margin: 2rem auto;
                padding: 2rem;
                border-radius: 18px;
                box-shadow: 0 8px 32px 0 rgba(99,91,255,0.15);
            }}
            h1, h2 {{
                color: #635bff;
            }}
            .section-title {{
                font-size: 1.2rem;
                font-weight: bold;
                margin-top: 1.2rem;
            }}
        </style>
    </head>
    <body>
        <h1>{title}</h1>
        {"<p><i>Source : " + source + "</i></p>" if source else ""}
    """

    # Découpage en sections (améliore au besoin)
    blocks = summary_text.split("\n")
    for block in blocks:
        block = block.strip()
        if not block:
            continue
        if block.lower().startswith("résumé"):
            html += f"<div class='section-title'>Résumé</div><p>{block.split(':',1)[-1].strip()}</p>"
        elif block.lower().startswith("moléc"):
            html += f"<div class='section-title'>Molécules mentionnées</div><p>{block.split(':',1)[-1].strip()}</p>"
        elif block.lower().startswith("patho"):
            html += f"<div class='section-title'>Pathologies ciblées</div><p>{block.split(':',1)[-1].strip()}</p>"
        elif block.lower().startswith("type"):
            html += f"<div class='section-title'>Type d'étude</div><p>{block.split(':',1)[-1].strip()}</p>"
        elif block.lower().startswith("auteur"):
            html += f"<div class='section-title'>Auteurs principaux</div><p>{block.split(':',1)[-1].strip()}</p>"
        else:
            html += f"<p>{block}</p>"

    html += "</body></html>"
    buffer = BytesIO(html.encode('utf-8'))
    buffer.seek(0)
    return buffer
