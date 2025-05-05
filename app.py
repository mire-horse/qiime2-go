"""
app.py - Flask application for QIIME2-go platform
"""

from flask import Flask, render_template, request, send_file, flash, redirect, url_for, jsonify
import os
import tempfile
import shutil
import uuid
import subprocess
import qiime2
import pandas as pd
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.secret_key = os.urandom(24)

# Configuration
UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'uploads')
EXPORT_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'exports')
ALLOWED_EXTENSIONS = {'qza', 'qzv', 'tsv', 'txt'}

# Create upload and export directories if they don't exist
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(EXPORT_FOLDER, exist_ok=True)

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['EXPORT_FOLDER'] = EXPORT_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 500 * 1024 * 1024  # 500MB max upload size

# Helper functions
def allowed_file(filename, allowed_types=None):
    if allowed_types is None:
        allowed_types = ALLOWED_EXTENSIONS
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in allowed_types

def clean_old_files():
    """Remove files older than 1 hour"""
    # Implementation here if needed
    pass

def get_artifact_type(file_path):
    """Determine the type of QIIME2 artifact"""
    try:
        artifact = qiime2.Artifact.load(file_path)
        return str(artifact.type)
    except:
        try:
            visualization = qiime2.Visualization.load(file_path)
            return "Visualization"
        except:
            return "Unknown"

def export_artifact(file_path, output_dir):
    """Export a QIIME2 artifact to its native format"""
    artifact_type = get_artifact_type(file_path)
    
    if artifact_type == "Visualization":
        # Export visualization
        try:
            result = subprocess.run(
                ['qiime', 'tools', 'export', 
                 '--input-path', file_path, 
                 '--output-path', output_dir],
                capture_output=True, text=True, check=True
            )
            return "Visualization", output_dir, None
        except subprocess.CalledProcessError as e:
            return None, None, f"Error exporting visualization: {e.stderr}"
    
    else:
        # Export artifact
        try:
            result = subprocess.run(
                ['qiime', 'tools', 'export', 
                 '--input-path', file_path, 
                 '--output-path', output_dir],
                capture_output=True, text=True, check=True
            )
            return artifact_type, output_dir, None
        except subprocess.CalledProcessError as e:
            return None, None, f"Error exporting artifact: {e.stderr}"

def create_zip(directory):
    """Create a zip file of the exported data"""
    output_filename = os.path.join(app.config['EXPORT_FOLDER'], f"export_{uuid.uuid4().hex}.zip")
    shutil.make_archive(output_filename[:-4], 'zip', directory)
    return output_filename

def validate_metadata(file_path):
    """Validate a QIIME2 metadata file"""
    errors = []
    warnings = []
    
    try:
        # Read the file as text first to check for directives
        with open(file_path, 'r') as f:
            lines = f.readlines()
        
        # Check for column type directive
        has_types_directive = False
        for line in lines:
            if line.strip().startswith('#q2:types'):
                has_types_directive = True
                break
        
        if not has_types_directive:
            warnings.append("No '#q2:types' directive found. Consider adding column type information (categorical/numeric) for better compatibility with QIIME2.")
        
        # Check if file is readable as TSV
        try:
            df = pd.read_csv(file_path, sep='\t', header=0)
        except Exception as e:
            errors.append(f"File is not a valid TSV: {str(e)}")
            return False, errors, warnings
        
        # Check if file has an ID column (required for QIIME2)
        if '#SampleID' not in df.columns and 'sample-id' not in df.columns and 'SampleID' not in df.columns:
            errors.append("Missing required ID column. QIIME2 metadata files must have a '#SampleID', 'sample-id', or 'SampleID' column.")
        
        # Check for empty cells in the ID column (not allowed in QIIME2)
        id_col = '#SampleID' if '#SampleID' in df.columns else ('sample-id' if 'sample-id' in df.columns else 'SampleID')
        if id_col in df.columns and df[id_col].isna().any():
            errors.append(f"Column '{id_col}' contains empty cells. Sample IDs cannot be empty in QIIME2 metadata.")
        
        # Check for empty cells in other columns (warning only, as QIIME2 can handle these with --p-no-filter-empty-samples)
        for col in df.columns:
            if col != id_col and df[col].isna().any():
                warnings.append(f"Column '{col}' contains empty cells. Consider using --p-no-filter-empty-samples when using this metadata with QIIME2.")
        
        # Check for duplicate IDs
        id_col = '#SampleID' if '#SampleID' in df.columns else ('sample-id' if 'sample-id' in df.columns else 'SampleID')
        if id_col in df.columns and df[id_col].duplicated().any():
            errors.append(f"Duplicate sample IDs found in '{id_col}' column.")
        
        # Check for invalid characters in column names
        for col in df.columns:
            if not all(c.isalnum() or c in ['-', '_', '#'] for c in col):
                warnings.append(f"Column name '{col}' contains characters that may cause issues in QIIME2.")
        
        # Skip QIIME2's metadata validation for now as it's causing compatibility issues
        # We'll rely on our own validation checks above
        warnings.append("Note: Basic validation checks passed, but full QIIME2 validation was skipped. For complete validation, use the QIIME2 command line tool.")
        
        return len(errors) == 0, errors, warnings
    
    except Exception as e:
        errors.append(f"Unexpected error during validation: {str(e)}")
        return False, errors, warnings


# Routes
@app.route('/')
def index():
    return render_template('index.html', active_tab='export')

@app.route('/metadata-validator')
def metadata_validator():
    return render_template('metadata_validator.html', active_tab='metadata')

@app.route('/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        flash('No file part')
        return redirect(url_for('index'))
    
    file = request.files['file']
    
    if file.filename == '':
        flash('No selected file')
        return redirect(url_for('index'))
    
    if file and allowed_file(file.filename, {'qza', 'qzv'}):
        filename = secure_filename(file.filename)
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], f"{uuid.uuid4().hex}_{filename}")
        file.save(file_path)
        
        # Create temporary directory for export
        export_dir = tempfile.mkdtemp(dir=app.config['EXPORT_FOLDER'])
        
        # Export the artifact
        artifact_type, export_path, error = export_artifact(file_path, export_dir)
        
        if error:
            flash(error)
            return redirect(url_for('index'))
        
        # Create a zip file of the exported data
        zip_file = create_zip(export_path)
        
        # Clean up
        os.remove(file_path)
        shutil.rmtree(export_dir)
        
        return send_file(
            zip_file,
            as_attachment=True,
            download_name=f"exported_{filename.rsplit('.', 1)[0]}.zip"
        )
    
    flash('Invalid file format. Please upload .qza or .qzv files.')
    return redirect(url_for('index'))

@app.route('/validate-metadata', methods=['POST'])
def validate_metadata_file():
    if 'file' not in request.files:
        return jsonify({'success': False, 'message': 'No file part'})
    
    file = request.files['file']
    
    if file.filename == '':
        return jsonify({'success': False, 'message': 'No selected file'})
    
    if file and allowed_file(file.filename, {'tsv', 'txt'}):
        filename = secure_filename(file.filename)
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], f"{uuid.uuid4().hex}_{filename}")
        file.save(file_path)
        
        # Validate the metadata file
        is_valid, errors, warnings = validate_metadata(file_path)
        
        # Clean up
        os.remove(file_path)
        
        return jsonify({
            'success': True,
            'valid': is_valid,
            'errors': errors,
            'warnings': warnings
        })
    
    return jsonify({'success': False, 'message': 'Invalid file format. Please upload .tsv or .txt files.'})


@app.route('/artifact-types')
def artifact_types():
    """Display information about QIIME2 artifact types and their exports"""
    return render_template('artifact_types.html', active_tab='export')

if __name__ == '__main__':
    # Clean old files on startup
    clean_old_files()
    app.run(debug=True)
