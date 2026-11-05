import unittest
from calculations import weigh, inventory
from domain import DomainError


class TestCalculations(unittest.TestCase):

    def test_weigh_compatible(self):
        # Test essential: 20000 - 12000 para 10 m3 => 8000 kg e faixa 6500 - 9500
        res = weigh(volume_m3=10, gross_kg=20000, tare_kg=12000)
        self.assertEqual(res["gross_kg"], 20000)
        self.assertEqual(res["tare_kg"], 12000)
        self.assertIsInstance(res["gross_kg"], (int, float))
        self.assertIsInstance(res["tare_kg"], (int, float))
        self.assertEqual(res["net_kg"], 8000)
        self.assertEqual(res["net_t"], 8.0)
        self.assertEqual(res["min_kg"], 6500)
        self.assertEqual(res["max_kg"], 9500)
        self.assertEqual(res["status"], "compatible")
        self.assertEqual(res["difference_kg"], 0)
        self.assertEqual(res["density_min"], 650)
        self.assertEqual(res["density_max"], 950)
        self.assertIn("formula", res)
        self.assertIn("notice", res)

    def test_weigh_divergent(self):
        # Test essential: 25000 - 12000 para 10 m3 => divergente 3500 kg
        res = weigh(volume_m3=10, gross_kg=25000, tare_kg=12000)
        self.assertEqual(res["net_kg"], 13000)
        self.assertEqual(res["status"], "divergent")
        self.assertEqual(res["difference_kg"], 3500)

        # Abaixo do mínimo: 18000 - 12000 = 6000 kg (mínimo 6500 kg => divergente 500 kg)
        res_below = weigh(volume_m3=10, gross_kg=18000, tare_kg=12000)
        self.assertEqual(res_below["net_kg"], 6000)
        self.assertEqual(res_below["status"], "divergent")
        self.assertEqual(res_below["difference_kg"], 500)

    def test_weigh_invalid_inputs(self):
        # Gross <= Tare
        with self.assertRaises(DomainError) as ctx:
            weigh(volume_m3=10, gross_kg=12000, tare_kg=12000)
        self.assertEqual(ctx.exception.status, 422)
        self.assertEqual(ctx.exception.code, "validation_error")

        # Negative / zero volume
        with self.assertRaises(DomainError):
            weigh(volume_m3=0, gross_kg=20000, tare_kg=12000)
        with self.assertRaises(DomainError):
            weigh(volume_m3=-5, gross_kg=20000, tare_kg=12000)

        # Booleans rejected
        with self.assertRaises(DomainError):
            weigh(volume_m3=True, gross_kg=20000, tare_kg=12000)
        with self.assertRaises(DomainError):
            weigh(volume_m3=10, gross_kg=False, tare_kg=12000)

        # NaN / Inf rejected
        with self.assertRaises(DomainError):
            weigh(volume_m3=float('nan'), gross_kg=20000, tare_kg=12000)
        with self.assertRaises(DomainError):
            weigh(volume_m3=10, gross_kg=float('inf'), tare_kg=12000)

        # Density bounds invalid
        with self.assertRaises(DomainError):
            weigh(volume_m3=10, gross_kg=20000, tare_kg=12000, density_min=0)
        with self.assertRaises(DomainError):
            weigh(volume_m3=10, gross_kg=20000, tare_kg=12000, density_min=900, density_max=800)

    def test_inventory(self):
        # Test essential: inventário 60/15/.7 => 2.9688 m³
        res = inventory(diameter_cm=60, height_m=15, form_factor=0.7)
        self.assertEqual(res["volume_m3"], 2.9688)
        self.assertAlmostEqual(res["min_mass_t"], round(2.9688 * 650 / 1000.0, 4), places=4)
        self.assertAlmostEqual(res["max_mass_t"], round(2.9688 * 950 / 1000.0, 4), places=4)
        self.assertIn("pi*(dap/100)^2*H*f/4", res["formula"])
        self.assertIn("não modifica crédito", res["notice"].lower())

    def test_inventory_invalid_inputs(self):
        # 0 < f <= 1
        with self.assertRaises(DomainError):
            inventory(diameter_cm=60, height_m=15, form_factor=0)
        with self.assertRaises(DomainError):
            inventory(diameter_cm=60, height_m=15, form_factor=1.1)
        with self.assertRaises(DomainError):
            inventory(diameter_cm=60, height_m=15, form_factor=-0.5)

        # non-positive diameter or height
        with self.assertRaises(DomainError):
            inventory(diameter_cm=0, height_m=15, form_factor=0.7)
        with self.assertRaises(DomainError):
            inventory(diameter_cm=60, height_m=-1, form_factor=0.7)

        # Booleans / NaN / Inf
        with self.assertRaises(DomainError):
            inventory(diameter_cm=True, height_m=15, form_factor=0.7)
        with self.assertRaises(DomainError):
            inventory(diameter_cm=60, height_m=float('nan'), form_factor=0.7)

    def test_inventory_huge_inputs_reject_overflow(self):
        # Finite but giant inputs (e.g. 1e308) must raise DomainError, not OverflowError
        with self.assertRaises(DomainError) as ctx:
            inventory(diameter_cm=1e308, height_m=15, form_factor=0.7)
        self.assertEqual(ctx.exception.status, 422)

        with self.assertRaises(DomainError) as ctx:
            inventory(diameter_cm=60, height_m=1e308, form_factor=0.7)
        self.assertEqual(ctx.exception.status, 422)




if __name__ == "__main__":
    unittest.main()
