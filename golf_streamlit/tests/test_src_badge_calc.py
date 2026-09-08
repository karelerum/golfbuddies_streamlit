import unittest

import pandas as pd

from src import badge_calc


class SrcBadgeCalcTests(unittest.TestCase):
    def test_calculate_achievements_handles_scopes_and_exclusive_groups(self):
        spillere_df = pd.DataFrame(
            [
                {"Kallenavn": "A"},
                {"Kallenavn": "B"},
            ]
        )

        resultater_df = pd.DataFrame(
            [
                {
                    "rundeid": "R1",
                    "turneringsid": "T1",
                    "spiller": "A",
                    "hole_in_one": 0,
                    "eagle": 0,
                    "birdie": 3,
                    "par_ind": 6,
                    "p6": 10,
                    "slag": 70,
                    "spiller_par": -2,
                    "other_ind": 5,
                },
                {
                    "rundeid": "R1",
                    "turneringsid": "T1",
                    "spiller": "B",
                    "hole_in_one": 0,
                    "eagle": 0,
                    "birdie": 1,
                    "par_ind": 4,
                    "p6": 8,
                    "slag": 73,
                    "spiller_par": 1,
                    "other_ind": 2,
                },
                {
                    "rundeid": "R2",
                    "turneringsid": "T1",
                    "spiller": "A",
                    "hole_in_one": 0,
                    "eagle": 0,
                    "birdie": 2,
                    "par_ind": 5,
                    "p6": 9,
                    "slag": 71,
                    "spiller_par": -1,
                    "other_ind": 1,
                },
                {
                    "rundeid": "R2",
                    "turneringsid": "T1",
                    "spiller": "B",
                    "hole_in_one": 0,
                    "eagle": 0,
                    "birdie": 0,
                    "par_ind": 2,
                    "p6": 7,
                    "slag": 75,
                    "spiller_par": 3,
                    "other_ind": 0,
                },
            ]
        )

        merker_df = pd.DataFrame(
            [
                {
                    "kategori": "antall_par",
                    "verdi": 5,
                    "vinner_innen": "runde",
                    "visningsnavn": "5 Par",
                    "filnavn": "5_par.png",
                    "merke_id": 101,
                    "eksklusiv_gruppe": "",
                    "prioritet": 0,
                },
                {
                    "kategori": "plassering",
                    "verdi": 1,
                    "vinner_innen": "runde",
                    "visningsnavn": "Rundevinner",
                    "filnavn": "rundevinner.png",
                    "merke_id": 103,
                    "eksklusiv_gruppe": "",
                    "prioritet": 0,
                },
                {
                    "kategori": "plassering",
                    "verdi": 1,
                    "vinner_innen": "turnering",
                    "visningsnavn": "Turneringsvinner",
                    "filnavn": "turneringsvinner.png",
                    "merke_id": 104,
                    "eksklusiv_gruppe": "",
                    "prioritet": 0,
                },
                {
                    "kategori": "antall_birdie",
                    "verdi": 3,
                    "vinner_innen": "totalt",
                    "visningsnavn": "Birdie Nivaa 1",
                    "filnavn": "birdie_nivaa_1.png",
                    "merke_id": 201,
                    "eksklusiv_gruppe": "birdie_nivaa",
                    "prioritet": 1,
                },
                {
                    "kategori": "antall_birdie",
                    "verdi": 5,
                    "vinner_innen": "totalt",
                    "visningsnavn": "Birdie Nivaa 2",
                    "filnavn": "birdie_nivaa_2.png",
                    "merke_id": 202,
                    "eksklusiv_gruppe": "birdie_nivaa",
                    "prioritet": 2,
                },
            ]
        )

        achievements_df = badge_calc.calculate_achievements(
            df_spillere=spillere_df,
            df_resultater=resultater_df,
            df_merker=merker_df,
        )

        self.assertEqual(
            list(achievements_df.columns),
            ["spiller", "rundeid", "turneringsid", "merke_id", "vinner_innen", "visningsnavn", "filnavn"],
        )

        a_df = achievements_df.loc[achievements_df["spiller"] == "A"].copy()
        b_df = achievements_df.loc[achievements_df["spiller"] == "B"].copy()

        self.assertEqual(len(b_df), 0)

        # runde-merke (antall_par >= 5) skal gi 2 rader for A (R1 og R2)
        self.assertEqual(len(a_df.loc[a_df["merke_id"] == 101]), 2)

        # rundevinner skal gi 2 rader for A (R1 og R2)
        self.assertEqual(len(a_df.loc[a_df["merke_id"] == 103]), 2)

        # turneringsvinner skal gi 1 rad for A i T1
        self.assertEqual(len(a_df.loc[a_df["merke_id"] == 104]), 1)

        # eksklusiv gruppe birdie_nivaa: kun høyeste prioritet beholdes
        self.assertEqual(len(a_df.loc[a_df["merke_id"] == 201]), 0)
        self.assertEqual(len(a_df.loc[a_df["merke_id"] == 202]), 1)

        # vinner_innen fra "totalt" skal normaliseres til "total"
        nivaa_df = a_df.loc[a_df["merke_id"] == 202]
        self.assertEqual(nivaa_df.iloc[0]["vinner_innen"], "total")

    def test_calculate_achievements_fills_missing_turneringsid_from_rundeid(self):
        spillere_df = pd.DataFrame([{"Kallenavn": "A"}])

        resultater_df = pd.DataFrame(
            [
                {
                    "rundeid": "T12345-01",
                    "turneringsid": pd.NA,
                    "spiller": "A",
                    "hole_in_one": 0,
                    "eagle": 0,
                    "birdie": 0,
                    "par_ind": 0,
                    "p6": 0,
                    "slag": 72,
                    "spiller_par": 0,
                    "other_ind": 0,
                }
            ]
        )

        merker_df = pd.DataFrame(
            [
                {
                    "kategori": "plassering",
                    "verdi": 1,
                    "vinner_innen": "turnering",
                    "visningsnavn": "Turneringsvinner",
                    "filnavn": "turneringsvinner.png",
                    "merke_id": 104,
                    "eksklusiv_gruppe": "",
                    "prioritet": 0,
                }
            ]
        )

        achievements_df = badge_calc.calculate_achievements(
            df_spillere=spillere_df,
            df_resultater=resultater_df,
            df_merker=merker_df,
        )

        self.assertEqual(len(achievements_df), 1)
        self.assertEqual(achievements_df.iloc[0]["turneringsid"], "T12345")

    def test_calculate_achievements_round_winner_is_unique(self):
        spillere_df = pd.DataFrame(
            [
                {"Kallenavn": "A"},
                {"Kallenavn": "B"},
            ]
        )

        # Samme p6 for begge spillere i samme runde; lavest slag skal vinne.
        resultater_df = pd.DataFrame(
            [
                {
                    "rundeid": "R1",
                    "turneringsid": "T1",
                    "spiller": "A",
                    "hole_in_one": 0,
                    "eagle": 0,
                    "birdie": 0,
                    "par_ind": 0,
                    "p6": 10,
                    "slag": 70,
                    "spiller_par": 0,
                    "other_ind": 0,
                },
                {
                    "rundeid": "R1",
                    "turneringsid": "T1",
                    "spiller": "B",
                    "hole_in_one": 0,
                    "eagle": 0,
                    "birdie": 0,
                    "par_ind": 0,
                    "p6": 10,
                    "slag": 72,
                    "spiller_par": 0,
                    "other_ind": 0,
                },
            ]
        )

        merker_df = pd.DataFrame(
            [
                {
                    "kategori": "plassering",
                    "verdi": 1,
                    "vinner_innen": "runde",
                    "visningsnavn": "Rundevinner",
                    "filnavn": "rundevinner.png",
                    "merke_id": 103,
                    "eksklusiv_gruppe": "",
                    "prioritet": 0,
                }
            ]
        )

        achievements_df = badge_calc.calculate_achievements(
            df_spillere=spillere_df,
            df_resultater=resultater_df,
            df_merker=merker_df,
        )

        winner_rows = achievements_df.loc[achievements_df["merke_id"] == 103]
        self.assertEqual(len(winner_rows), 1)
        self.assertEqual(winner_rows.iloc[0]["spiller"], "A")

    def test_round_placement_badges_respect_delturnering_filter(self):
        spillere_df = pd.DataFrame(
            [
                {"Kallenavn": "A"},
                {"Kallenavn": "B"},
                {"Kallenavn": "C"},
            ]
        )

        # To runder, en i delturnering 1 og en i delturnering 2.
        resultater_df = pd.DataFrame(
            [
                # Delturnering 1
                {"rundeid": "R1", "turneringsid": "2024-1A", "spiller": "A", "hole_in_one": 0, "eagle": 0, "birdie": 0, "par_ind": 0, "p6": 30, "slag": 70, "spiller_par": 0, "other_ind": 0},
                {"rundeid": "R1", "turneringsid": "2024-1A", "spiller": "B", "hole_in_one": 0, "eagle": 0, "birdie": 0, "par_ind": 0, "p6": 20, "slag": 71, "spiller_par": 0, "other_ind": 0},
                {"rundeid": "R1", "turneringsid": "2024-1A", "spiller": "C", "hole_in_one": 0, "eagle": 0, "birdie": 0, "par_ind": 0, "p6": 10, "slag": 72, "spiller_par": 0, "other_ind": 0},
                # Delturnering 2
                {"rundeid": "R2", "turneringsid": "2024-2A", "spiller": "A", "hole_in_one": 0, "eagle": 0, "birdie": 0, "par_ind": 0, "p6": 30, "slag": 70, "spiller_par": 0, "other_ind": 0},
                {"rundeid": "R2", "turneringsid": "2024-2A", "spiller": "B", "hole_in_one": 0, "eagle": 0, "birdie": 0, "par_ind": 0, "p6": 20, "slag": 71, "spiller_par": 0, "other_ind": 0},
                {"rundeid": "R2", "turneringsid": "2024-2A", "spiller": "C", "hole_in_one": 0, "eagle": 0, "birdie": 0, "par_ind": 0, "p6": 10, "slag": 72, "spiller_par": 0, "other_ind": 0},
            ]
        )

        merker_df = pd.DataFrame(
            [
                {"kategori": "plassering", "verdi": 1, "vinner_innen": "runde", "delturnering": "1", "visningsnavn": "Rundens vinner", "filnavn": "r1.png", "merke_id": 9, "eksklusiv_gruppe": "", "prioritet": 0},
                {"kategori": "plassering", "verdi": 2, "vinner_innen": "runde", "delturnering": "1", "visningsnavn": "Rundens nr2", "filnavn": "r2.png", "merke_id": 10, "eksklusiv_gruppe": "", "prioritet": 0},
                {"kategori": "plassering", "verdi": 3, "vinner_innen": "runde", "delturnering": "1", "visningsnavn": "Rundens nr3", "filnavn": "r3.png", "merke_id": 11, "eksklusiv_gruppe": "", "prioritet": 0},
                {"kategori": "plassering", "verdi": 1, "vinner_innen": "runde", "delturnering": "2", "visningsnavn": "Vinter Rundens Vinner", "filnavn": "v1.png", "merke_id": 12, "eksklusiv_gruppe": "", "prioritet": 0},
                {"kategori": "plassering", "verdi": 2, "vinner_innen": "runde", "delturnering": "2", "visningsnavn": "Vinter Rundens nr2", "filnavn": "v2.png", "merke_id": 13, "eksklusiv_gruppe": "", "prioritet": 0},
                {"kategori": "plassering", "verdi": 3, "vinner_innen": "runde", "delturnering": "2", "visningsnavn": "Vinter Rundens nr3", "filnavn": "v3.png", "merke_id": 14, "eksklusiv_gruppe": "", "prioritet": 0},
            ]
        )

        achievements_df = badge_calc.calculate_achievements(
            df_spillere=spillere_df,
            df_resultater=resultater_df,
            df_merker=merker_df,
        )

        del1_rows = achievements_df.loc[
            achievements_df["turneringsid"].astype(str).str[5:6].eq("1")
        ]
        del2_rows = achievements_df.loc[
            achievements_df["turneringsid"].astype(str).str[5:6].eq("2")
        ]

        self.assertEqual(
            len(del1_rows.loc[del1_rows["merke_id"].isin([12, 13, 14])]),
            0,
        )
        self.assertEqual(
            len(del2_rows.loc[del2_rows["merke_id"].isin([9, 10, 11])]),
            0,
        )

    def test_exclusive_group_turnering_is_unique_per_turnering(self):
        spillere_df = pd.DataFrame([{"Kallenavn": "A"}])

        resultater_df = pd.DataFrame(
            [
                {
                    "rundeid": "R1",
                    "turneringsid": "2024-1A",
                    "spiller": "A",
                    "hole_in_one": 0,
                    "eagle": 0,
                    "birdie": 3,
                    "par_ind": 0,
                    "p6": 10,
                    "slag": 70,
                    "spiller_par": 0,
                    "other_ind": 0,
                },
                {
                    "rundeid": "R2",
                    "turneringsid": "2024-2A",
                    "spiller": "A",
                    "hole_in_one": 0,
                    "eagle": 0,
                    "birdie": 3,
                    "par_ind": 0,
                    "p6": 9,
                    "slag": 71,
                    "spiller_par": 0,
                    "other_ind": 0,
                },
            ]
        )

        merker_df = pd.DataFrame(
            [
                {
                    "kategori": "antall_birdie",
                    "verdi": 1,
                    "vinner_innen": "turnering",
                    "visningsnavn": "Birdie Nivaa 1",
                    "filnavn": "birdie_1.png",
                    "merke_id": 301,
                    "eksklusiv_gruppe": "birdie_nivaa",
                    "prioritet": 1,
                },
                {
                    "kategori": "antall_birdie",
                    "verdi": 3,
                    "vinner_innen": "turnering",
                    "visningsnavn": "Birdie Nivaa 2",
                    "filnavn": "birdie_2.png",
                    "merke_id": 302,
                    "eksklusiv_gruppe": "birdie_nivaa",
                    "prioritet": 2,
                },
            ]
        )

        achievements_df = badge_calc.calculate_achievements(
            df_spillere=spillere_df,
            df_resultater=resultater_df,
            df_merker=merker_df,
        )

        # Skal være ett badge per turnering i samme eksklusive gruppe.
        t1 = achievements_df.loc[achievements_df["turneringsid"] == "2024-1A"]
        t2 = achievements_df.loc[achievements_df["turneringsid"] == "2024-2A"]

        self.assertEqual(len(t1.loc[t1["merke_id"] == 302]), 1)
        self.assertEqual(len(t2.loc[t2["merke_id"] == 302]), 1)

    def test_calculate_achievements_awards_only_the_best_qualifying_break_badge(self):
        spillere_df = pd.DataFrame([{"Kallenavn": "Kåre"}])
        resultater_df = pd.DataFrame(
            [{"rundeid": "20260104", "turneringsid": "202601", "spiller": "Kåre", "slag": 87}]
        )
        merker_df = pd.DataFrame(
            [
                {"kategori": "antall_slag", "verdi": 75, "vinner_innen": "runde", "visningsnavn": "Break 75", "filnavn": "break_75.png", "merke_id": 75},
                {"kategori": "antall_slag", "verdi": 80, "vinner_innen": "runde", "visningsnavn": "Break 80", "filnavn": "break_80.png", "merke_id": 80},
                {"kategori": "antall_slag", "verdi": 90, "vinner_innen": "runde", "visningsnavn": "Break 90", "filnavn": "break_90.png", "merke_id": 90},
                {"kategori": "antall_slag", "verdi": 100, "vinner_innen": "runde", "visningsnavn": "Break 100", "filnavn": "break_100.png", "merke_id": 100},
            ]
        )

        achievements_df = badge_calc.calculate_achievements(
            df_spillere=spillere_df,
            df_resultater=resultater_df,
            df_merker=merker_df,
        )

        self.assertEqual(achievements_df["filnavn"].tolist(), ["break_90.png"])
        self.assertEqual(achievements_df["rundeid"].tolist(), ["20260104"])


if __name__ == "__main__":
    unittest.main()
