import sys
import os
from pathlib import Path
import json
import numpy as np
# import random
import requests
# from time import sleep
from PIL import Image
from PIL.ImageQt import ImageQt

# from fbs_runtime.application_context.PyQt5 import ApplicationContext
from PyQt5.QtWidgets import QApplication, QWidget, QDialog, QFormLayout, QGridLayout, QLabel, QDoubleSpinBox, QFileDialog
from PyQt5.QtWidgets import  QCheckBox, QPushButton, QHBoxLayout, QVBoxLayout, QScrollArea, QLineEdit, QComboBox, QProgressBar
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QPixmap


class QuickQuestion(QDialog):
    procDone = pyqtSignal(int)

    def __init__(self, text="", answers=[], **kwargs):
        super(QuickQuestion, self).__init__()
        self.kwargs = kwargs

        self.lay = QVBoxLayout()
        self.setLayout(self.lay)

        self.text = QLabel(text)
        self.text.setStyleSheet(" font-size: 50px;")
        self.text.setWordWrap(True)

        self.lay.addWidget(self.text)

        self.value = None

        for ii, row in enumerate(answers):
            butt = QPushButton(row)
            butt.id = ii            
            
            butt.clicked.connect(self.clickeroni)

            self.lay.addWidget(butt)

    def set_value(self, x):
        self.value = x

    def get_value(self):
        return self.value

    # Set up pushbutton function
    def clickeroni(self):
        self.value = self.sender().id
        self.procDone.emit(self.value)


class QuickQuiz(QDialog):
    mainSignal = pyqtSignal(int)

    def __init__(self, quiz_config=None, **kwargs):
        super(QuickQuiz, self).__init__()
        self.kwargs = kwargs

        self.working_dir = Path(os.path.realpath(
                                    os.path.join(os.getcwd(), os.path.dirname(__file__)))) 

        # Read in config
        if isinstance(quiz_config, dict): # If handed a dict read it directly
            self.config = quiz_config

        else: # else I'm assuming you're handing me a filepath and I'll try to read it
            self.config_file = Path(quiz_config)

            if not self.config_file.is_absolute():
                self.config_file = self.working_dir / self.config_file

            with open(self.config_file) as ff:
                self.config = json.load(ff)

        # Store key info from config
        self.options = self.config.get("Options", {})
        self.questions = self.config.get("Questions", [])
        self.results = self.config.get("Results", {})

        # Setup Question Order
        self.n_qs = len(self.questions)
        self.q_order = np.arange(self.n_qs)
        if self.options.get("Random Order", False):
            np.random.shuffle(self.q_order)

        # Setup Layout
        self.lay = QVBoxLayout()
        self.setLayout(self.lay)

        # Add Title Label
        self.title = self.config.get("Quiz Name", "")
        self.setWindowTitle(self.title)

        title_lab = QLabel(self.title)
        title_lab.setStyleSheet(" font-size: 100px; qproperty-alignment: AlignCenter;")
        self.lay.addWidget(title_lab)

        # Setup Progressbar
        self.cur_q_idx = -1
        self.max_qs = self.options.get("Max Questions", np.inf)
        

        # Determine after how many questions to stop
        if self.max_qs < self.n_qs : # Number has been limited in the config, stop at the defined limit
            self.pbar_end = self.max_qs
        else: # number of questions hasn't been limited, stop when you've run out of questions
            self.pbar_end = self.n_qs

        self.pbar = QProgressBar()
        self.lay.addWidget(self.pbar)

        # Figure out the largest number of answers for any question
        n_ans = [len(q["answers"]) for q in self.questions]
        self.max_ans = max(n_ans)

        # Setup containers
        self.answers = np.zeros(self.n_qs) * np.nan

        self.next_question()

        # print("done.")

    def tabulate_score(self):
        """
        Take an array of scores and return a seed
        """
        # Generate the bit formatting string
        n_bits = int(np.ceil(np.log2(self.max_ans)))
        fmt_str = "{0:0"+str(n_bits)+"b}"
        
        # Convert answers to int
        self.answers = self.answers.astype(np.int64)

        # Convert each element in answers to a bit string
        bits = [fmt_str.format(ans) for ans in self.answers]
        bit_string = "".join(bits)
            
        # Convert the combined bit string back to an integer
        seed = int(bit_string, 2)

        return seed

    def next_question(self):
        """
        Detect that a question has been answered and populate the next question
        """
        # Grab the old question
        wid = self.lay.itemAt(1)
        if wid is not None and isinstance(wid.widget(), QuickQuestion) :
            # Save off the answer
            idx = self.q_order[self.cur_q_idx]
            # self.answers.append(wid.widget().get_value())
            self.answers[idx] = wid.widget().get_value()
            # print(self.answers[-1])

            # Delete the old question
            wid.widget().deleteLater()
            self.lay.removeItem(wid)


        # Update the index and progressbar
        self.cur_q_idx += 1
        self.pbar.setValue(100 * self.cur_q_idx / self.pbar_end)


        # Check if you've reached the last question
        if self.cur_q_idx >= self.pbar_end:
            self.show_results()
            # self.populate_img()
            return


        # populate the next question
        idx = self.q_order[self.cur_q_idx]
        q = self.questions[idx]
        wid = QuickQuestion(text="\n"+q["text"]+"\n", answers=q["answers"])
        wid.procDone.connect(self.next_question)

        self.lay.insertWidget(1, wid)


    def show_results(self):
        
        # delete pbar
        # Grab the old question
        wid = self.lay.itemAt(1)
        if wid is not None and isinstance(wid.widget(), QProgressBar) :
            # Delete the old question
            wid.widget().deleteLater()
            self.lay.removeItem(wid)

        # Get the answers array and convert it to a seed
        seed = self.tabulate_score()

        # Get weightings of all possible options
        wgts = np.array([x["weight"] for x in self.results])
        wgts = wgts / np.sum(wgts) # normalize the array

        # Randomly generate an answer based on the seed
        np.random.seed(seed)
        choice = np.random.choice(np.arange(len(wgts)), p=wgts)
        # print(choice)
        result = self.results[choice]
        self.result = result

        # Add widgets
        header = self.config.get("Results Header", "")
        head_lab = QLabel(header)
        head_lab.setStyleSheet(" font-size: 60px;")
        head_lab.setWordWrap(True)
        self.lay.addWidget(head_lab)

        result_lab = QLabel(result["Name"])
        result_lab.setStyleSheet(" font-size: 55px; qproperty-alignment: AlignCenter;")
        self.lay.addWidget(result_lab)

        # print(result)
        if result.get("image", None):
            try:
                img_url = result["image"]
                img = self.load_img_url(img_url)
                
                # Rescale image
                scale = 480 / img.height
                new_size = (int(img.width*scale), int(img.height*scale))
                img = img.resize(new_size)

                imgQt = ImageQt(img)

                pix = QPixmap.fromImage(imgQt)
                self.pix_lab = QLabel()
                self.pix_lab.setPixmap(pix)
                self.lay.addWidget(self.pix_lab, alignment=Qt.AlignCenter)
            except Exception as e:
                print(e)

            # print(f"Yo, we got an image here! {img}")

        if result.get("description", None):
            result_lab = QLabel(result["description"])
            result_lab.setStyleSheet(" font-size: 40px;")
            self.lay.addWidget(result_lab)


        bot_but_lay = QHBoxLayout()

        quit_butt = QPushButton("Quit")
        quit_butt.clicked.connect(self.close)
        bot_but_lay.addWidget(quit_butt)

        retry_butt = QPushButton("Try again")
        retry_butt.clicked.connect(self.reset)
        bot_but_lay.addWidget(retry_butt)

        self.lay.addLayout(bot_but_lay)

        # sleep(0.1)

    def reset(self):
        self.cur_q_idx = -1

        # Delete all previous widgets
        for ii in range(1, self.lay.count()):
            wid = self.lay.itemAt(1)
            if wid is not None:
                if isinstance(wid, QHBoxLayout):
                    # Clear out sublayout
                    for jj in range(wid.count()):
                        swid = wid.itemAt(0)
                        if swid is not None:
                            swid.widget().deleteLater()
                            wid.removeItem(swid)
                    # Delete layout
                    self.lay.removeItem(wid)

                else:
                    # Delete the old question
                    wid.widget().deleteLater()
                    self.lay.removeItem(wid)

        # Readd progress bar
        self.pbar = QProgressBar()
        self.lay.addWidget(self.pbar)

        self.answers = np.zeros(self.n_qs) * np.nan
        self.next_question()

    def load_img_url(self, url):
        return Image.open(requests.get(url, stream=True).raw)

    # def populate_img(self):
    #     img_url = self.result["image"]
    #     img = self.load_img_url(img_url)
    #     # imgQt = ImageQt(img.resize((144,192)))
    #     imgQt = ImageQt(img)

    #     pix = QPixmap.fromImage(imgQt)
    #     # pix.scaledToHeight(64)

    #     self.pix_lab.setPixmap(pix)

if __name__ == '__main__':
    # appctxt = ApplicationContext()       # 1. Instantiate ApplicationContext
    # window = QMainWindow()
    # window.resize(250, 150)
    # window.show()
    # exit_code = appctxt.app.exec_()      # 2. Invoke appctxt.app.exec_()
    # sys.exit(exit_code)   

     #==============================================================================================

    app = QApplication(sys.argv)
    diag = QuickQuiz("whatjediareyou.json")
    # diag = QuickQuiz("whydonthiswork.json")
    diag.exec_()

    #==============================================================================================

    # # Grab web images
    # results = diag.results
    # headers = {'accept': 'application/json'}

    # for ii, char in enumerate(results):
    #     if not char.get("link", None):
    #         name = char["Name"]
    #         site_name = name.replace(" ","_")

    #         # Get wookiepedia site content
    #         url = "https://starwars.fandom.com/wiki/" + site_name
    #         results[ii]["link"] = url
    #     else:
    #         url = char["link"]
            
    #     if not char.get("image", None):
    #         # results[ii]["image"] = None
    #         site = requests.get(url, headers=headers)

    #         # Extract "og:image" URL
    #         idx = site.text.find("og:image")
    #         # slice up to og:image
    #         temp = site.text[idx:]
    #         idx = temp.find('"/>')
    #         temp = temp[:idx]

    #         img_url = temp.replace('og:image" content="',"")
    #         # self.img = self.load_img_url(img_url)
    #         # self.imgQt = ImageQt(self.img.resize((144,192)))

    #         results[ii]["image"] = img_url

    # with open("chars.json", "w") as ff:
    #     json.dump(results, ff, indent=4)

    #==============================================================================================

    # with open(r"F:\Documents_F\Python\trunk\Quizzer\src\main\python\whatjediareyou.json") as ff:
    #     config = json.load(ff)

    # for char in config["Results"]:
    #     try:
    #         img_url = char["image"]
    #         img = Image.open(requests.get(img_url, stream=True).raw)
            
    #         # Rescale image
    #         scale = 480 / img.height
    #         new_size = (int(img.width*scale), int(img.height*scale))
    #         img = img.resize(new_size)

    #         imgQt = ImageQt(img)

    #         pix = QPixmap.fromImage(imgQt)
    #         pix_lab = QLabel()
    #         pix_lab.setPixmap(pix)
    #         # lf.lay.addWidget(self.pix_lab, alignment=Qt.AlignCenter)

    #         print(char["Name"] + " is fine.")

    #     except Exception as e:
    #         print(char["Name"] + " FAILED!")
    #         print(e)


    # print("done.")