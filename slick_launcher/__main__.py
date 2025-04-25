import snoop

snoop.install()

from .slick_launcher import main
import sys
show_settings=False
if len(sys.argv) >1 and sys.argv[1]=="settings":
    show_settings = True
if __name__=="__main__":
    main(show_settings)