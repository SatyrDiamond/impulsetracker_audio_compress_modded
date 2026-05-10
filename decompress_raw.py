import func
import argparse

parser = argparse.ArgumentParser()
parser.add_argument("-i", default=None)
parser.add_argument("-o", default=None)
args = parser.parse_args()

func.decode_file(args.i, args.o if args.o else args.i.replace('.wav', '.pcm'))