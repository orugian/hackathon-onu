import unittest
from documents import render_passport

class PassportDocumentTests(unittest.TestCase):
    def test_print_view_preserves_fields_and_escapes_declared_text(self):
        passport = {
            'id': 'PASS-TEST', 'schema_version': '1.0.0', 'issued_at': '2026-11-05T12:00:00+00:00',
            'lot_id': 'AM-DEMO-001', 'plot_id': 'AREA-DEMO-001',
            'origin': {'name': 'Área demonstrativa', 'simulated': True},
            'authorization': {'reference': 'AUT-DEMO-001', 'issuer': 'Referência fictícia', 'status': 'não verificável'},
            'recipient': '<script>alert(1)</script>', 'product': 'Madeira em tora', 'species': 'Táxon não verificado',
            'vehicle': 'VEICULO-DEMO', 'invoice': 'NF-DEMO', 'volume_m3': 10, 'volume_milli': 10000,
            'weighing': {'gross_kg':20000,'tare_kg':12000,'net_kg':8000,'min_kg':6500,'max_kg':9500,'status':'compatible','notice':'Hipótese, não prova legalidade'},
            'balance_after_milli': 5000, 'event_id': 2, 'hash': 'a'*64, 'notice': 'SEM VALIDADE OFICIAL', 'simulated': True
        }
        html = render_passport(passport)
        self.assertIn('SEM VALIDADE OFICIAL', html)
        self.assertIn('Passaporte experimental de produto florestal', html)
        self.assertIn('20.000', html)
        self.assertIn('12.000', html)
        self.assertIn('8.000', html)
        self.assertIn('5,000', html)
        self.assertIn('a'*64, html)
        self.assertIn('&lt;script&gt;', html)
        self.assertNotIn('<script>alert(1)</script>', html)
        self.assertIn('/api/passports/PASS-TEST', html)
        self.assertIn('/static/passport.js', html)

if __name__ == '__main__': unittest.main()
