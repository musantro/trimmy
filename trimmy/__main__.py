import sys


def main():
    from video_trimmer.main_window import run

    path = sys.argv[1] if len(sys.argv) > 1 else None
    run(path)


if __name__ == "__main__":
    main()
