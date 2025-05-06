import snoop

snoop.install()

from .slick_launcher import main
import sys
if __name__=="__main__":
    main(sys.argv)