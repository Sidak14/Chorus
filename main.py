import pandas as pd
from spotdl import Spotdl
from pydub import AudioSegment
import librosa
import numpy as np
import os

class FastSongProcessor:
    def __init__(self):
        self.spot = Spotdl(
            client_id="1e7160661b5849e7a50f41de5b8f9ef1",
            client_secret="6c04a0251cda402688b667a8a4df52ec"
        )
    
    def download_song(self, song_name, artist):
        try:
            search_query = f"{song_name} {artist}"
            print(f"Searching for: {search_query}")
            
            songs = self.spot.search([search_query])
            if not songs:
                print(f"Could not find {search_query}")
                return None, None
            
            song = songs[0]
            path = self.spot.download(song)[1]
            print(f"Downloaded to: {path}")
            return path, song.name
            
        except Exception as e:
            print(f"Error downloading {song_name}: {e}")
            return None, None

    def detect_chorus(self, audio_segment):
        try:
            samples = np.array(audio_segment.get_array_of_samples())
            
            if audio_segment.channels == 2:
                samples = samples.reshape((-1, 2)).mean(axis=1)
            
            samples = samples.astype(float) / np.max(np.abs(samples))
            
            mel_spec = librosa.feature.melspectrogram(
                y=samples,
                sr=audio_segment.frame_rate,
                n_mels=128,
                fmax=8000
            )
            
            onset_env = librosa.onset.onset_strength(
                y=samples, 
                sr=audio_segment.frame_rate,
                aggregate=np.median
            )
            
            peaks = librosa.util.peak_pick(
                onset_env,
                pre_max=30,
                post_max=30,
                pre_avg=30,
                post_avg=30,
                delta=0.2,
                wait=30
            )
            
            peak_times = librosa.frames_to_time(peaks, sr=audio_segment.frame_rate) * 1000
            
            if len(peak_times) > 0:
                song_length = len(audio_segment)
                target_position = song_length * 0.3
                estimated_chorus = peak_times[
                    np.argmin(np.abs(peak_times - target_position))
                ]
                
                print(f"Detected chorus at: {estimated_chorus/1000:.2f} seconds")
                return estimated_chorus
            else:
                default_position = len(audio_segment) * 0.3
                print(f"No peaks found, using default position: {default_position/1000:.2f} seconds")
                return default_position
            
        except Exception as e:
            print(f"Error in chorus detection: {e}")
            return None

    def extract_chorus(self, audio_segment, chorus_start_ms, duration_ms=60000, pre_chorus_duration = 20000):
        try:
            post_chorus_duration = duration_ms - pre_chorus_duration
            
            # Calculate start and end points
            start_ms = max(0, int(chorus_start_ms - pre_chorus_duration))
            end_ms = min(int(chorus_start_ms + post_chorus_duration), len(audio_segment))
            
            print(f"Extracting extended chorus section:")
            print(f"  Full song length: {len(audio_segment)/1000:.2f}s")
            print(f"  Chorus detected at: {chorus_start_ms/1000:.2f}s")
            print(f"  Extract from: {start_ms/1000:.2f}s to {end_ms/1000:.2f}s")
            print(f"  Extract duration: {(end_ms-start_ms)/1000:.2f}s")
            
            chorus = audio_segment[start_ms:end_ms]
            chorus = chorus.fade_in(500).fade_out(500)
            chorus = chorus.normalize()
            
            return chorus
        except Exception as e:
            print(f"Error extracting chorus: {e}")
            return None


def mix_segments(chorus_files, crossfade_duration=5000):
    """
    Mix audio segments with crossfading, reading from files
    crossfade_duration: duration of crossfade in milliseconds (default 5 seconds)
    """
    if not chorus_files:
        return None
    
    print("\nMixing segments:")
    print(f"Number of segments to mix: {len(chorus_files)}")
    print(f"Crossfade duration: {crossfade_duration/1000}s")
    
    # Load the first segment
    final_mix = AudioSegment.from_wav(chorus_files[0])
    current_position = len(final_mix)
    
    # Add each subsequent segment with crossfade
    for i, file_path in enumerate(chorus_files[1:], 1):
        # Load next segment
        next_segment = AudioSegment.from_wav(file_path)
        
        # Calculate overlap position
        overlap_position = current_position - crossfade_duration
        
        print(f"Adding segment {i+1}/{len(chorus_files)}")
        print(f"  Current mix length: {current_position/1000:.2f}s")
        print(f"  Adding segment length: {len(next_segment)/1000:.2f}s")
        print(f"  Overlap starts at: {overlap_position/1000:.2f}s")
        
        # Overlay the next segment
        final_mix = final_mix.append(next_segment, crossfade=crossfade_duration)
        
        # Update position for next segment
        current_position = len(final_mix)
        print(f"  New mix length: {current_position/1000:.2f}s")
    
    # Final processing
    print("\nApplying final processing:")
    print("  - Normalizing volume")
    final_mix = final_mix.normalize()
    
    print("  - Adding fade in/out")
    final_mix = final_mix.fade_in(2000).fade_out(2000)
    
    print(f"Final mix duration: {len(final_mix)/1000:.2f}s")
    return final_mix

def main():
    try:
        df = pd.read_excel('ed_sheeran_songs.xlsx')
    except Exception as e:
        print(f"Error reading Excel file: {e}")
        return

    processor = FastSongProcessor()
    all_songs = []
    chorus_files = []

    # First download all songs
    for _, row in df.iterrows():
        song_name = row['song_name']
        artist = row['artist']
        
        print(f"\nProcessing: {song_name} by {artist}")
        path, song_title = processor.download_song(song_name, artist)
        if path:
            all_songs.append((path, song_title))

    # Then process each song for chorus extraction
    for song_path, song_title in all_songs:
        try:
            # Generate chorus filename
            chorus_filename = f"chorus_{song_title.replace(' ', '_')}.wav"
            
            # Check if chorus file already exists
            if os.path.exists(chorus_filename):
                print(f"Chorus file already exists for {song_title}, skipping extraction")
                chorus_files.append(chorus_filename)
                continue
            
            print(f"\nExtracting chorus from: {song_title}")
            audio = AudioSegment.from_mp3(song_path)
            chorus_start = processor.detect_chorus(audio)
            
            if chorus_start is not None:
                chorus = processor.extract_chorus(audio, chorus_start)
                if chorus is not None:
                    # Save individual chorus
                    chorus.export(chorus_filename, format="wav")
                    print(f"✓ Saved chorus to: {chorus_filename}")
                    
                    # Store the file path
                    chorus_files.append(chorus_filename)
            
        except Exception as e:
            print(f"Error processing {song_path}: {e}")
            continue

    # Mix all choruses together
    if len(chorus_files) >= 2:
        print("\nCreating final mix...")
        final_mix = mix_segments(chorus_files)
        if final_mix:
            output_filename = "ed_sheeran_mega_mix.wav"
            final_mix.export(output_filename, format="wav")
            print("✓ Successfully created mega mix!")
            print(f"Output saved as: {output_filename}")
            
            # Print final file size
            file_size = os.path.getsize(output_filename) / (1024 * 1024)
            print(f"Final file size: {file_size:.2f} MB")
    else:
        print("Not enough chorus segments to create a mix")

if __name__ == "__main__":
    main()