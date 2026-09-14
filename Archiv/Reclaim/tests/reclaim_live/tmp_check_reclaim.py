# -*- coding: utf-8 -*-
import io
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
s = open(r"test/tmp_kanten_engine_replay.py", encoding="utf-8",
         newline="").read().split("\r\n")
for i in range(2010, 2030):
    print(i + 1, repr(s[i]))
