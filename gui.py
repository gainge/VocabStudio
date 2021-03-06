import tkinter as tk
from tkinter import messagebox
from tkinter import simpledialog
import threading
import time
import datetime
import os
import pyaudio
import wave
import numpy as np

class Recorder(tk.Frame):
    MODE_APPEND = "append"
    MODE_PREPEND = "prepend"
    MODE_RE_RECORD = "rerecord"
    _LABEL_COLOR = "#AEF3E7"

    _COUNTDOWN_STEPS = 3
    _COUNTDOWN_BEEP = 0.1
    _COUNTDOWN_TOTAL = 0.15
    _RECORD_BEEP = 0.5

    _RECORDING_BREAK = 44100 * 4
    _TERM_DEF_DELAY = 0.9

    def __init__(self, parent, *args, **kwargs):
        tk.Frame.__init__(self, parent, *args, **kwargs)

        self.parent = parent
        self.recordings = []
        self.recordingLabels = []
        self.selectedIndex = None
        self.isRecording = False

        # Audio recording params
        self.chunk = 1024  # Record in chunks of 1024 samples
        self.sample_format = pyaudio.paInt16  # 16 bits per sample
        self.channels = 1 # Change this to match your input device
        self.fs = 44100  # Record at 44100 samples per second

        sizex = 800
        sizey = 600
        self.root = tk.Frame(self.parent, width=sizex, height=sizey, padx=10, pady=10)
    
        self.myframe = tk.Frame(self.root, relief=tk.GROOVE, width=50, height=100, bd=1)
        self.myframe.grid(row=0, rowspan=5, column=0, padx=(0, 10), pady=(0, 10))

        self.canvas = tk.Canvas(self.myframe)
        self.frame = tk.Frame(self.canvas)
        self.myscrollbar = tk.Scrollbar(self.myframe, orient="vertical", command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=self.myscrollbar.set)

        self.myscrollbar.pack(side="right", fill="y")
        self.canvas.pack(side="left")
        self.canvas.create_window((0,0), window=self.frame, anchor='nw')

        self.frame.bind("<Configure>", self.configureScroll)

        self.root.bind_all("<Key>", self.keyPress)


        # Let's try throwing in some buttons
        self.recordButton = tk.Button(self.root, command=self.newRecording, text='Start Recording', bg='blue')
        self.recordButton.grid(row=6, column=0, sticky='ew', padx=(0, 10))

        self.whiteNoiseButton = tk.Button(self.root, command= lambda: self.newRecording(self.setWhiteNoise), text="White Noise")
        # self.whiteNoiseButton.grid(row=6, column=1, sticky='ew')

        # Ok, let's actually have it be like a radio button thing
        self.radioLabel = tk.Label(self.root, text="MODE", bg='#ccc')
        self.radioLabel.grid(row=0, column=1, sticky='ew')

        self.radioGroup = tk.Frame(self.root)

        self.MODES = [
            ("Append", Recorder.MODE_APPEND),
            ("Prepend", Recorder.MODE_PREPEND),
            ("Re-Record", Recorder.MODE_RE_RECORD),
        ]

        self.currentMode = tk.StringVar()
        self.currentMode.set(Recorder.MODE_APPEND)

        for label, mode in self.MODES:
            rb = tk.Radiobutton(
                self.radioGroup, 
                text=label, 
                variable=self.currentMode, 
                value=mode,
                
                )
            rb.pack(anchor='w')

        self.radioGroup.grid(row=1, column=1)


        # Init the play button
        self.playButton = tk.Button(self.root, command=self.playRecording, text="Play", fg='blue')
        self.playButton.grid(row=2, column=1, sticky='ew')

        # Delete button
        self.deleteButton = tk.Button(self.root, command=self.onDelete, text="Delete", fg='red')
        self.deleteButton.grid(row=3, column=1, sticky='ew')

        # Save button
        self.saveButton = tk.Button(self.root, command=self.saveAudio, text="Save", fg='green')
        self.saveButton.grid(row=4, column=1, sticky='ew')

        self.root.pack()

    def saveAudio(self):
        # Disable key bindings on root
        self.root.unbind_all("<Key>")

        confirm = tk.messagebox.askyesno(title="Save", message="Do you want to save the current recordings?")
        
        if confirm:
            saveFile = simpledialog.askstring(title="Save Audio", prompt="Please Enter a File Name")

            if not saveFile:
                # Set to timestamp
                saveFile = str(int(time.time()))

            # Sanitize for spaces
            saveFile = saveFile.replace(" ", "-") + ".wav"

            self.writeAudio(saveFile)


        # Re-attach bindings to roots
        self.root.bind_all("<Key>", self.keyPress)


    def _createSilence(self, duration=44100):
        return bytes([0] * duration)
    
    def writeAudio(self, fileName):
        if len(self.recordings) == 0:
            messagebox.showerror("Error", "Please make some recordings!")
            return
        # So uhhhh yeah here we go
        # Long break followed by relativelyshort break
        shortBreak = self._createSilence(self._RECORDING_BREAK) # I think this will be sufficient

        # Now we just have to write out all the ish
        p = pyaudio.PyAudio()

        wf = wave.open(fileName, 'wb')
        wf.setnchannels(self.channels)
        wf.setsampwidth(p.get_sample_size(self.sample_format))
        wf.setframerate(self.fs)

        p.terminate()

        wf.writeframes(b''.join(self.recordings[0]))
        wf.writeframes(shortBreak)

        # Now for all the terms
        for i in range(1, len(self.recordings)):
            currentRecording = self.recordings[i]
            recordingBytes = b''.join(currentRecording)
            wf.writeframes(recordingBytes)
            
            if i % 2 == 1:
                # Create the repeat delay if on a term
                recordingLength = len(recordingBytes)

                # Doing floor division here ensures the sample is an even number of frames
                # I think this will help in keeping things from being corrupted
                delayLength = max((recordingLength // self.fs) * self.fs, self._RECORDING_BREAK)
                delay = self._createSilence(delayLength)
                wf.writeframes(delay)
            else:
                # Write the standard intra-term break
                wf.writeframes(shortBreak)

        wf.close()
        


        return

    def onDelete(self):
        print("Deleting Selected Recording")
        self.deleteRecording(self.selectedIndex)

    def addRecording(self, recording, index=None):
        if index is None: index = self.selectedIndex

        mode = self.currentMode.get()
        print(mode + "  " + str(index))

        if mode == self.MODE_APPEND and index is None: index = 0

        # Create new label object
        newLabel = tk.Label(self.frame, text=("(" + self._timestamp() + ")"))

        # Insert Recording and label at specified index, according to mode
        if mode == self.MODE_APPEND:
            self.recordings.insert(index + 1, recording)
            self.recordingLabels.insert(index + 1, newLabel)
        elif mode == self.MODE_PREPEND:
            self.recordings.insert(index, recording)
            self.recordingLabels.insert(index, newLabel)
        elif mode == self.MODE_RE_RECORD:
            self.recordings[index] = recording
            self.recordingLabels[index] = newLabel
        else:
            # Default, standard end of list append
            index = len(self.recordings)
            self.recordings.insert(index, recording)
            self.recordingLabels.insert(index, newLabel)
        
        self.updateRecordingsGrid()

        if len(self.recordings) == 1 and mode == self.MODE_APPEND:
            index = -1 # edge case for first recording

        # Update selected index
        self.selectedIndex = index
        if mode == self.MODE_APPEND: self.selectedIndex += 1

        # And darken the selection
        self.darken(self.selectedIndex)

    def deleteRecording(self, index=None):
        if index is None:
            index = self.selectedIndex
        
        if index is None:
            messagebox.showerror("Error", "Please make some recordings!")
            return
        
        # Otherwise we remove the homie from our two lists
        del self.recordings[index]
        del self.recordingLabels[index]

        # assert length match
        assert len(self.recordings) == len(self.recordingLabels)

        # Update lists
        self.updateRecordingsGrid()

        # Update selection
        if self.selectedIndex == 0:
            self.selectedIndex = None
        else:
            self.selectedIndex -= 1
            self.darken(self.selectedIndex)

    
    def updateRecordingsGrid(self):
        # Update Grid by iterating over children
        for widget in self.frame.children.values():
            # Forget the configured grid placement
            widget.grid_forget()

        # Create a new grid placement
        for newIndex, item in enumerate(self.recordingLabels):
            prefix = "Title"

            if newIndex == 0:
                # Handle the case of the title recording
                item.grid(row=0, column=0, columnspan=2, sticky='ew')
            else:
                row = ((newIndex - 1) / 2) + 1
                col = (newIndex - 1) % 2
                # Reset grid position
                item.grid(row=int(row), column=int(col))

                # Prepend the correct term, depending on the new index
                prefix = "Term" if (newIndex - 1) % 2 == 0 else "Def."
                prefix = prefix + " " + str(int(((newIndex - 1) / 2)) + 1)
            
            # Update Label for Item
            labelText = item.cget("text")
            # Extract the timestamp
            labelText = labelText[labelText.find('('):]
            # Add on the prefix to the timestamp
            labelText = prefix + " " + labelText
            # Set the label text
            item.config(text=labelText)
            
            # Reset binding to select correct index
            item.bind("<Button-1>", lambda event, index=newIndex: self.selectRecording(index))
            
            


    def callback(self):
        self.parent.quit()

    def testButton(self, e=None):
        print("hey there! " + self.currentMode.get())

    def darken(self, index):
        # Check the index
        if index < 0 or index >= len(self.recordings):
            raise ValueError("Invalid Index!")

        # Clear existing backgrounds
        for recordingLabel in self.recordingLabels:
            recordingLabel.configure(background='white')

        self.recordingLabels[index].configure(background=Recorder._LABEL_COLOR)

    def selectRecording(self, index):
        # Check the index
        if index < 0 or index >= len(self.recordings):
            raise ValueError("Invalid Index!")
        
        # update selection
        self.selectedIndex = index

        # Darken
        self.darken(index)

    def configureScroll(self, event):
        self.canvas.configure(scrollregion=self.canvas.bbox("all"),width=200,height=200)

    def keyPress(self, e):
        if (e.keycode == KEY_SHIFT_Q):
            # Unbind keypresses for dialog box
            self.root.unbind_all("<Key>")

            exitConfirm = tk.messagebox.askyesno(title="Exit", message="Are you sure you want to exit?")
            # Quit if confirm
            if exitConfirm: self.callback()
            else: self.root.bind_all("<Key>", self.keyPress) # rebind
        elif (e.keycode == KEY_P):
            self.playRecording()
        elif (e.keycode == KEY_LEFT):
            # Move selection down one index
            self._moveSelectionDown()
        elif (e.keycode == KEY_UP):
            # Move selection down two indices
            self._moveSelectionDown()
            self._moveSelectionDown()
        elif (e.keycode == KEY_DOWN):
            # Move selection up two indices
            self._moveSelectionUp()
            self._moveSelectionUp()
        elif (e.keycode == KEY_RIGHT):
            # Move selection up one index
            self._moveSelectionUp()
        
        print('press', e.keycode)

    def _moveSelectionUp(self):
        if (self.selectedIndex is not None) and (self.selectedIndex < len(self.recordings) - 1): 
                self.selectRecording(self.selectedIndex + 1)


    def _moveSelectionDown(self):
        if self.selectedIndex: 
            self.selectRecording(self.selectedIndex - 1)

    def setWhiteNoise(self, whiteNoise):
        self.whiteNoise = whiteNoise
        self.whiteNoiseButton.config(fg='green')

    def newRecording(self, callback=None):
        if callback is None:
            callback = self.addRecording
        self.isRecording = not self.isRecording

        print("Turning Recording " + ("on" if self.isRecording else "off") + "!")

        if self.isRecording:
            # Spawn a new recording thread
            # This thread will be responsible for creating the recording and adding it to the list
            thread = threading.Thread(target=self.recordAudio, args=(callback,), daemon=True)
            thread.start()

            # Update Button Appearance
            self.recordButton.config(text="Stop Recording", fg='red')
        else:
            self.recordButton.config(text="Start Recording", fg='black')


    def tone(self, duration = 1.0, freq = 440.0):
        p = pyaudio.PyAudio()

        volume = 0.5     # range [0.0, 1.0]
        sr = 44100       # sampling rate, Hz, must be integer

        # generate samples, note conversion to float32 array
        samples = (np.sin(2*np.pi*np.arange(sr*duration)*freq/sr)).astype(np.float32)

        # for paFloat32 sample values must be in range [-1.0, 1.0]
        stream = p.open(format=pyaudio.paFloat32,
                        channels=1,
                        rate=sr,
                        output=True)

        # play. May repeat with different volume values (if done interactively) 
        stream.write(volume*samples)

        stream.stop_stream()
        stream.close()

        p.terminate()
    
    def recordAudio(self, callback):
        # Count down the recording
        countdown = Recorder._COUNTDOWN_STEPS
        countTotal = Recorder._COUNTDOWN_TOTAL
        countLen = Recorder._COUNTDOWN_BEEP

        for i in range(countdown):
            print(str(i + 1) + "... ")
            duration = countLen
            self.tone(duration)
            time.sleep(countTotal - duration)

        self.tone(Recorder._RECORD_BEEP, 880)

        p = pyaudio.PyAudio()  # Create an interface to PortAudio

        # Start recording
        stream = p.open(format=self.sample_format,
                        channels=self.channels,
                        rate=self.fs,
                        frames_per_buffer=self.chunk,
                        input=True)

        frames = []  # Initialize array to store frames

        while self.isRecording:
            data = stream.read(self.chunk)
            frames.append(data)
        
        # Stop and close the stream 
        stream.stop_stream()
        stream.close()
        # Terminate the PortAudio interface
        p.terminate()

        # Pass the data into the callback
        callback(frames)

    def printNums(self, count=10):
        thread = threading.Thread(target=self.threadPrint, args=(count,), daemon=True)
        thread.start()

    def _timestamp(self):
        return datetime.datetime.now().strftime('%H:%M:%S')

    def threadPrint(self, count=10):
        for i in range(10):
            print(i)
            time.sleep(1)

    def playRecording(self, index=None):
        if index is None:
            index = self.selectedIndex
        
        if index is None:
            messagebox.showerror("Error", "Please make some recordings!")
            return
        
        p = pyaudio.PyAudio()

        stream = p.open(format=self.sample_format,
                        channels=self.channels,
                        rate=self.fs,
                        output=True)

        stream.write(b''.join(self.recordings[index]))

        stream.stop_stream()
        stream.close()

        p.terminate()


def initMicAccess():
    # Open PyAudio Stream to attempt to get permissions access
    p = pyaudio.PyAudio()

    stream = p.open(
        rate=44100,
        channels=1,
        format=pyaudio.paInt16,
        input=True
    )
    stream.stop_stream()
    stream.close()

    p.terminate()



KEY_SPACE = 32
KEY_DELETE = 3342463
KEY_P = 112
KEY_SHIFT_Q = 81
KEY_LEFT = 8124162
KEY_RIGHT = 8189699
KEY_UP = 8320768
KEY_DOWN = 8255233


POS_X = 300
POS_Y = 200


master = tk.Tk()
master.title("Vocab Track Builder")
recorder = Recorder(master)
recorder.pack(side="top", fill="both", expand=True)

initMicAccess()

master.mainloop()



print("Tried so hard and got so far")








