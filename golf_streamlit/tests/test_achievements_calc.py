import unittest

import pandas as pd

from aiapi.achievements_calc import calculate_achievements


class AchievementCalcTests(unittest.TestCase):
	def test_calculate_achievements_awards_expected_badges(self):
		result_df = pd.DataFrame(
			[
				{
					"rundeid": "R1",
					"spiller": "A",
					"hole_in_one": 1,
					"eagle": 0,
					"birdie": 3,
					"par_ind": 6,
					"p6": 10,
					"slag": 70,
					"par": 72,
				},
				{
					"rundeid": "R1",
					"spiller": "B",
					"hole_in_one": 0,
					"eagle": 1,
					"birdie": 1,
					"par_ind": 10,
					"p6": 8,
					"slag": 73,
					"par": 72,
				},
				{
					"rundeid": "R2",
					"spiller": "A",
					"hole_in_one": 0,
					"eagle": 0,
					"birdie": 0,
					"par_ind": 2,
					"p6": 7,
					"slag": 76,
					"par": 72,
				},
				{
					"rundeid": "R2",
					"spiller": "B",
					"hole_in_one": 0,
					"eagle": 0,
					"birdie": 2,
					"par_ind": 4,
					"p6": 9,
					"slag": 71,
					"par": 72,
				},
			]
		)

		round_info_df = pd.DataFrame(
			[
				{"rundeid": "R1", "turneringsid": "T1", "runde": 1, "ferdig_ind": 1},
				{"rundeid": "R2", "turneringsid": "T2", "runde": 1, "ferdig_ind": 1},
			]
		)

		tournament_df = pd.DataFrame(
			[
				{"turneringsid": "T1", "turneringsnavn": "VO 2024", "type": "Sommer"},
				{"turneringsid": "T2", "turneringsnavn": "VO Vinter 24/25", "type": "Vinter"},
			]
		)

		badge_catalog_df = pd.DataFrame(
			[
				{"kategori": "unik", "verdi": None, "vinner_innen": "totalt", "visningsnavn": "Hole in one", "filnavn": "hio.png", "b": 1},
				{"kategori": "type_par", "verdi": -2, "vinner_innen": "totalt", "visningsnavn": "Eagle", "filnavn": "eagle.png", "b": 2},
				{"kategori": "antall_par", "verdi": 5, "vinner_innen": "runde", "visningsnavn": "5 Par", "filnavn": "5par.png", "b": 3},
				{"kategori": "antall_birdie", "verdi": 3, "vinner_innen": "runde", "visningsnavn": "3 Birdies", "filnavn": "3birdies.png", "b": 4},
				{"kategori": "antall_birdie", "verdi": 3, "vinner_innen": "totalt", "visningsnavn": "Birdie 3", "filnavn": "birdie3.png", "b": 5},
				{"kategori": "plassering", "verdi": 1, "vinner_innen": "runde", "visningsnavn": "Rundens vinner", "filnavn": "round1.png", "b": 6},
				{"kategori": "plassering", "verdi": 1, "vinner_innen": "runde", "visningsnavn": "Vinter Rundens Vinner", "filnavn": "winter1.png", "b": 7},
				{"kategori": "plassering", "verdi": 1, "vinner_innen": "turnering", "visningsnavn": "Vinner VO 2024", "filnavn": "vo2024.png", "b": 8},
			]
		)

		achievements_df = calculate_achievements(
			result_df=result_df,
			round_info_df=round_info_df,
			tournament_df=tournament_df,
			badge_catalog_df=badge_catalog_df,
		)

		self.assertEqual(list(achievements_df.columns), ["spiller", "merkeid", "vinner_innen_totalt"])

		as_tuples = {
			(row["spiller"], row["merkeid"], row["vinner_innen_totalt"])
			for _, row in achievements_df.iterrows()
		}

		self.assertIn(("A", "1", "totalt"), as_tuples)  # Hole in one
		self.assertIn(("A", "2", "totalt"), as_tuples)  # type_par from spiller_par=-2
		self.assertIn(("A", "3", "runde"), as_tuples)   # 5 par
		self.assertIn(("B", "3", "runde"), as_tuples)   # 5 par
		self.assertIn(("A", "4", "runde"), as_tuples)   # 3 birdies in round
		self.assertIn(("A", "5", "totalt"), as_tuples)  # 5 birdies total
		self.assertIn(("A", "6", "runde"), as_tuples)   # R1 winner
		self.assertIn(("B", "6", "runde"), as_tuples)   # R2 winner
		self.assertIn(("B", "7", "runde"), as_tuples)   # Winter round winner
		self.assertIn(("A", "8", "turnering"), as_tuples)  # Winner in VO 2024

	def test_calculate_achievements_awards_break_badges(self):
		result_df = pd.DataFrame(
			[
				{
					"rundeid": "R1",
					"spiller": "A",
					"hole_in_one": 0,
					"eagle": 0,
					"birdie": 1,
					"par_ind": 5,
					"p6": 10,
					"slag": 88,
					"par": 72,
				},
				{
					"rundeid": "R1",
					"spiller": "B",
					"hole_in_one": 0,
					"eagle": 0,
					"birdie": 0,
					"par_ind": 3,
					"p6": 8,
					"slag": 95,
					"par": 72,
				},
			]
		)

		round_info_df = pd.DataFrame(
			[
				{"rundeid": "R1", "turneringsid": "T1", "runde": 1, "ferdig_ind": 1},
			]
		)

		badge_catalog_df = pd.DataFrame(
			[
				{"kategori": "slag_total", "verdi": 75, "vinner_innen": "runde", "visningsnavn": "Break 75", "filnavn": "break_75.png", "b": 75},
				{"kategori": "slag_total", "verdi": 80, "vinner_innen": "runde", "visningsnavn": "Break 80", "filnavn": "break_80.png", "b": 80},
				{"kategori": "slag_total", "verdi": 90, "vinner_innen": "runde", "visningsnavn": "Break 90", "filnavn": "break_90.png", "b": 90},
				{"kategori": "slag_total", "verdi": 100, "vinner_innen": "runde", "visningsnavn": "Break 100", "filnavn": "break_100.png", "b": 100},
			]
		)

		achievements_df = calculate_achievements(
			result_df=result_df,
			round_info_df=round_info_df,
			badge_catalog_df=badge_catalog_df,
		)

		as_tuples = {
			(row["spiller"], row["merkeid"], row["vinner_innen_totalt"])
			for _, row in achievements_df.iterrows()
		}

		self.assertIn(("A", "90", "runde"), as_tuples)
		self.assertIn(("B", "100", "runde"), as_tuples)


if __name__ == "__main__":
	unittest.main()
