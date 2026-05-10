import func
import argparse

parser = argparse.ArgumentParser()
parser.add_argument("-i", default=None)
parser.add_argument("-o", default=None)
args = parser.parse_args()

func.encode_file_wav(args.i, args.o+'.it215' if args.o else args.i.replace('.wav', '.it215'))