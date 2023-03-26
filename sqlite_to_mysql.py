import re
import sys

def sqlite_to_mysql(fin, fout):
    for line in fin:
        line = re.sub(r"^(INSERT INTO .*?)\s+VALUES", r"\1\nVALUES", line)
        line = re.sub(r"INSERT INTO\s+", r"INSERT IGNORE INTO ", line)
        line = re.sub(r"DATETIME", r"TIMESTAMP", line)
        line = re.sub(r"([\(,]\s*)'t'(,\s*[\d\.]+|[,)]\s*)", r"\1CURRENT_TIMESTAMP\2", line)
        line = re.sub(r"([\(,]\s*)'f'(,\s*[\d\.]+|[,)]\s*)", r"\1\2", line)
        line = re.sub(r" AUTOINCREMENT", r" AUTO_INCREMENT", line)
        line = line.replace("CREATE TABLE sqlite_sequence", "CREATE TABLE IF NOT EXISTS sqlite_sequence")
        line = line.replace("INSERT INTO \"sqlite_sequence\"", "INSERT IGNORE INTO `sqlite_sequence`")
        line = re.sub(r"\"([^\"]+)\"", r"`\1`", line)
        fout.write(line)

if __name__ == "__main__":
    if len(sys.argv) != 3:
        print(f"Usage: {sys.argv[0]} input_file output_file")
        sys.exit(1)

    with open(sys.argv[1], "r") as fin, open(sys.argv[2], "w") as fout:
        sqlite_to_mysql(fin, fout)