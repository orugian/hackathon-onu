"""Proximity screening between a demonstration plot and real alert polygons."""
import unittest

from integrations import proximity_context

PLOT = {"type": "Feature", "properties": {"id": "P"}, "geometry": {"type": "Polygon", "coordinates": [[[0, 0], [0.01, 0], [0.01, 0.01], [0, 0.01], [0, 0]]]}}
MUNICIPALITY = {"type": "FeatureCollection", "features": [{"type": "Feature", "properties": {"codarea": "1"}, "geometry": {"type": "Polygon", "coordinates": [[[-1, -1], [1, -1], [1, 1], [-1, 1], [-1, -1]]]}}]}


def square(gid, x, y, date='2026-10-01', cls='DESMATAMENTO_CR'):
    s = 0.002
    return {"type": "Feature", "properties": {"gid": gid, "view_date": date, "classname": cls, "areamunkm": 0.1},
            "geometry": {"type": "Polygon", "coordinates": [[[x, y], [x + s, y], [x + s, y + s], [x, y + s], [x, y]]]}}


class ProximityTests(unittest.TestCase):
    def test_nearest_alert_and_radius_counts_are_reported_in_km(self):
        alerts = {"type": "FeatureCollection", "features": [
            square('near', 0.04, 0.0),    # ~3.3 km east of plot edge
            square('mid', 0.08, 0.0),     # ~7.7 km
            square('far', 0.5, 0.5),      # far away
        ]}
        result = proximity_context(PLOT, alerts, MUNICIPALITY, radii_km=(5, 10))
        self.assertEqual(result['nearest']['gid'], 'near')
        self.assertAlmostEqual(result['nearest']['distance_km'], 3.3, delta=0.2)
        self.assertEqual(result['within'], [{'radius_km': 5, 'count': 1}, {'radius_km': 10, 'count': 2}])
        self.assertTrue(result['plot_inside_municipality'])
        self.assertEqual(result['alerts_evaluated'], 3)
        self.assertIn('triagem', result['notice'])

    def test_overlapping_alert_has_zero_distance(self):
        alerts = {"type": "FeatureCollection", "features": [square('inside', 0.004, 0.004)]}
        self.assertEqual(proximity_context(PLOT, alerts, MUNICIPALITY)['nearest']['distance_km'], 0)

    def test_empty_sources_do_not_claim_absence(self):
        result = proximity_context(PLOT, {"type": "FeatureCollection", "features": []}, {"type": "FeatureCollection", "features": []})
        self.assertIsNone(result['nearest'])
        self.assertIsNone(result['plot_inside_municipality'])
        self.assertEqual(result['alerts_evaluated'], 0)


if __name__ == '__main__':
    unittest.main()
