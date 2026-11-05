"""Escaped, printable projection of the stored passport; never a second calculation."""
from html import escape
from urllib.parse import quote


def number(value, digits=0):
    return f'{value:,.{digits}f}'.replace(',', '_').replace('.', ',').replace('_', '.')


def render_passport(p):
    e = lambda value: escape(str(value), quote=True)
    w = p['weighing']
    rows = [
        ('Registro / versão', f"{p['id']} / {p['schema_version']}"),
        ('Emitido em UTC', p['issued_at']), ('Lote / área', f"{p['lot_id']} / {p['plot_id']}"),
        ('Origem demonstrativa', p['origin']['name']),
        ('Autorização de referência', f"{p['authorization']['reference']} · {p['authorization']['issuer']} · {p['authorization']['status']}"),
        ('Destinatário declarado', p['recipient']), ('Produto', p['product']),
        ('Espécie', p['species']), ('Volume reservado', number(p['volume_m3'], 3) + ' m³'),
        ('Veículo declarado', p['vehicle']), ('Referência fiscal declarada', p['invoice']),
        ('Peso bruto', number(w.get('gross_kg', 0), 3) + ' kg'), ('Tara', number(w.get('tare_kg', 0), 3) + ' kg'),
        ('Peso líquido', number(w['net_kg'], 3) + ' kg'),
        ('Faixa de massa hipotética', number(w['min_kg'], 3) + ' a ' + number(w['max_kg'], 3) + ' kg'),
        ('Conferência de massa', 'Compatível com a hipótese' if w['status'] == 'compatible' else 'Divergência — requer conferência'),
        ('Saldo após esta reserva', number(p['balance_after_milli'] / 1000, 3) + ' m³'),
        ('Evento vinculado', p['event_id'])
    ]
    table = ''.join(f'<tr><th scope="row">{e(label)}</th><td>{e(value)}</td></tr>' for label, value in rows)
    identifier = quote(p['id'], safe='')
    return f'''<!doctype html>
<html lang="pt-BR"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>RAIZTRACE · {e(p['id'])}</title><link rel="stylesheet" href="/static/passport.css"><script src="/static/passport.js" defer></script></head>
<body><nav aria-label="Ações do documento"><a href="/">Voltar ao RAIZTRACE</a><a href="/api/passports/{identifier}" download="{e(p['id'])}.json">Baixar JSON</a><button id="print-document" type="button">Imprimir / salvar PDF</button></nav>
<main><header><strong class="brand">RAIZTRACE</strong><span>Registro experimental · dados simulados</span></header>
<h1>Passaporte experimental de produto florestal</h1>
<p class="notice">SEM VALIDADE OFICIAL</p><p>Não substitui DOF, autorização ambiental, documento fiscal ou verificação de campo.</p>
<table><tbody>{table}</tbody></table>
<section aria-label="Integridade"><h2>Identidade do registro</h2><p>SHA-256 do JSON canônico, excluindo o próprio campo hash:</p><code>{e(p['hash'])}</code><p>O hash permite conferir o conteúdo; não autentica a origem nem impede a reconstrução do banco por quem o controla.</p></section>
<footer><p>{e(w['notice'])}</p><p>Saldo é o retrato no instante da reserva, não o saldo atual. Operação ilustrativa; nenhum documento real de terceiro foi validado.</p></footer></main></body></html>'''
