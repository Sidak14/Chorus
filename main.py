import pandas as pd
from song_processor import ConcurrentSongProcessor
import threading

def main():
    try:
        df = pd.read_excel('ed_sheeran_songs.xlsx')
    except Exception as e:
        print(f"Error reading Excel file: {e}")
        return

    processor = ConcurrentSongProcessor()
    
    # Fill download queue with all songs
    for _, row in df.iterrows():
        processor.download_queue.put((row['song_name'], row['artist']))

    # Process first song
    print("Processing first song...")
    if not processor.download_queue.empty():
        song_info = processor.download_queue.get()
        if processor.process_song(*song_info):
            print("First song processed, starting playback and concurrent downloads...")
        else:
            print("Failed to process first song, continuing with next...")

    # Start threads
    download_thread = threading.Thread(target=processor.download_thread)
    playback_thread = threading.Thread(target=processor.playback_thread)
    
    download_thread.start()
    playback_thread.start()
    
    try:
        # Wait for all processing to complete
        download_thread.join()
        playback_thread.join()
    except KeyboardInterrupt:
        print("\nStopping playback...")
    finally:
        processor.cleanup()

if __name__ == "__main__":
    main()