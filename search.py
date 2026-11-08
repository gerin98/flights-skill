import sys
import json
from flight_search import search_flights

def main():
    try:
        if len(sys.argv) < 4:
            print(json.dumps({"error": "Usage: search.py ORIGIN DEST DATE (YYYY-MM-DD)"}))
            return

        origin = sys.argv[1]
        dest = sys.argv[2]
        date = sys.argv[3]
        
        output = search_flights(origin, dest, date)
        print(json.dumps(output, indent=2))
        
    except Exception as e:
        print(json.dumps({"error": str(e)}))

if __name__ == "__main__":
    main()
