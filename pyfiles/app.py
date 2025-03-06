from flask import Flask, render_template, request, redirect
from pshare import *

from werkzeug.utils import secure_filename
import os
import glob


path = os.getcwd() 
parent = os.path.join(path, os.pardir) 
template_location = os.path.abspath(parent) + "/templates"
print(template_location)

app = Flask(__name__, template_folder=template_location)

""" Returns the list of files the user has stored on SNODES, if applicable """
@app.route('/')
def home():
    files = backend.pFiles() # dictionary: {filename: kb}
    return render_template('index.html', files=files)


""" Open a direct dialogue for the user to select a file to upload """
@app.route('/upload', methods=['POST'])
def upload():
    if request.method == "POST" and 'file' in request.files:
        try:
            f = request.files.get('file')
            if not f or f.filename == '':
                print('[DEBUG] no file selected')
                return redirect('/')

            print(f"[DEBUG] Received {f.filename}, storing to pyfiles/uploading_files")

            filename = secure_filename(f.filename) # prevent malicious entries
            dest = os.path.join(path, "uploading_files")
            full_path = os.path.join(dest, filename)

            f.save(full_path)

            print("[DEBUG] File stored locally, now uploading to SNODES")
            backend.pDistribute(absolute_path = full_path)

            # After uploading, empty the uploading_files folder
            uploaded_files = glob.glob(os.path.join(dest, '*')) #all files in dir
            for uploaded_file in uploaded_files:
                if os.path.isfile(uploaded_file):
                    os.remove(uploaded_file)


        except Exception as e:
            print(f"[DEBUG] While attempting to store file locally, encountered error: {e}")
            return redirect('/')


    
    return redirect('/')


""" Collects a list of file names and passes them to a utility function to download """
@app.route('/download', methods=['POST'])
def download():
    if request.method == "POST":
        selected_files = request.form.getlist('selected-file')
        backend.pRetrieve(selected_files)

    return redirect('/')


""" Collects the list of selected file names and passes it to a utility function for deletion,
returning the remaining files by redirecting to `/`"""
@app.route('/delete', methods=['POST'])
def delete():
    if request.method == "POST":
        selected_files = request.form.getlist('selected-file')
        backend.pDelete(selected_files)

    return redirect('/')


""" Returns the list of connected SNODES and provide modification options """
@app.route('/snodes', methods=['GET', 'POST'])
def snodes():
    connected_snodes = backend.pSnodes() 
    connected_snodes = connected_snodes if connected_snodes is not None else {}
    
    requested_snodes = backend.pAvailableSnodes()
    requested_snodes = requested_snodes if requested_snodes is not None else {}
    
    available_storage = backend.pAvailableStorage()
    used_storage = backend.pUsedStorage()

    return render_template('nodes.html', connected_nodes=connected_snodes, 
        available_nodes = requested_snodes, available_storage = available_storage, 
        used_storage = used_storage, type="s")


""" Returns the list of connected RNODES and provide modification options """
@app.route('/rnodes', methods=['GET', 'POST'])
def rnodes():
    connected_rnodes = backend.pRnodes()
    connected_rnodes = connected_rnodes if connected_rnodes is not None else {}
    
    available_rnodes = backend.pAvailableRnodes()
    available_rnodes = available_rnodes if available_rnodes is not None else {}

    return render_template('nodes.html', connected_nodes = connected_rnodes, available_nodes = available_rnodes, type="r")


@app.route('/add-snode', methods=['POST'])
def add_snode():
    selected_snodes = request.form.getlist('selected-available-node')
    print(selected_snodes)
    backend.pAddSnode(selected_snodes)
    return redirect('/snodes')

@app.route('/remove-snode', methods=['POST'])
def remove_snode():
    selected_snodes = request.form.getlist('selected-node')
    print(selected_snodes)
    backend.pRemoveSnode(selected_snodes)
    return redirect('/snodes')

@app.route('/add-rnode', methods=['POST'])
def add_rnode():
    selected_rnodes = request.form.getlist('selected-available-node')
    size_snode = request.form.get('StorageSize')
    print(selected_rnodes)
    print(size_snode)
    backend.pAddRnode(selected_rnodes, size_snode)
    return redirect('/rnodes')

@app.route('/remove-rnode', methods=['POST'])
def remove_rnode():
    selected_rnodes = request.form.getlist('selected-node')
    print(selected_rnodes)
    backend.pRemoveRnode(selected_rnodes)
    return redirect('/rnodes')

""" TODO: this will be replaced by a toggle accepting new connections button in the next sprint """
@app.route('/broadcast', methods=['POST'])
def broadcast():
    return redirect('/snodes')


if __name__ == '__main__':
    backend = pShare()
    app.run(debug=False)
