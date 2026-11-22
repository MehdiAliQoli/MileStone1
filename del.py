src = "data/seed/05_pharmacy_sales_data.csv"
dst = "data/seed/05_pharmacy_sales_data_small.csv"

with open(src, "r", encoding="utf-8") as fin, open(dst, "w", encoding="utf-8", newline="") as fout:
    fout.write(fin.readline())  # header
    for i, line in enumerate(fin):
        if i % 2 == 0:
            fout.write(line)