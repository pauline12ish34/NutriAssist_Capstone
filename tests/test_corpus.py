from nutriassist.training.corpus import clean_passages, pack_blocks, sample_runs

RW = "Abikorera bo mu karere ka Musanze barashimirwa ko bashora imari mu karere kabo aho kuyijyana ahandi"
RW_2 = "Umwana w'amezi atandatu agomba gutangira kurya ibindi biryo hamwe n'amashereka ya nyina buri munsi"


class TestSampleRuns:
    def test_runs_are_consecutive_rows_in_range(self):
        rows = sample_runs(num_rows=1000, rows_wanted=128, run_length=64, seed=1)
        assert len(rows) == 128 and len(set(rows)) == 128
        assert all(0 <= i < 1000 for i in rows)
        starts = [i for i in rows if i % 64 == 0]
        assert len(starts) == 2 and all(rows[rows.index(s) + 63] == s + 63 for s in starts)

    def test_same_seed_same_rows(self):
        assert sample_runs(10_000, 300, seed=7) == sample_runs(10_000, 300, seed=7)

    def test_asking_for_more_than_exists_returns_everything(self):
        assert sample_runs(100, 10_000, run_length=64) == list(range(64))   # one full run fits in 100 rows


class TestCleanPassages:
    def test_keeps_kinyarwanda_and_drops_short_english_and_duplicate_rows(self):
        rows = [RW, "Muraho neza.", "The district praised local investors for building hotels at home.", RW, RW_2]
        assert list(clean_passages(rows)) == [RW, RW_2]

    def test_drops_rows_containing_held_out_text(self):
        held_out = ["Umwana w'amezi atandatu agomba gutangira kurya ibindi biryo"]
        assert list(clean_passages([RW, RW_2.upper()], held_out)) == [RW]

    def test_short_held_out_text_does_not_remove_ordinary_sentences(self):
        assert list(clean_passages([RW], held_out=["mu karere"])) == [RW]


class TestPackBlocks:
    def test_blocks_are_full_with_separators_between_passages(self):
        blocks = pack_blocks([[1, 2, 3], [4, 5], [6, 7, 8, 9]], block_size=4, separator=0)
        assert blocks == [[1, 2, 3, 0], [4, 5, 0, 6], [7, 8, 9, 0]]

    def test_stops_at_max_blocks(self):
        assert pack_blocks([list(range(100))], block_size=10, separator=-1, max_blocks=3) == \
            [list(range(10)), list(range(10, 20)), list(range(20, 30))]
