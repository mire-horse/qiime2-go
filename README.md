# QIIME2-go

A not-so-comprehensive web platform for QIIME2 data processing that allows users to easily work with QIIME2 artifacts and metadata without using the command line. Mostly just a fun project I did in a night to see how well I understood the platform.

## Overview

QIIME2-go is a Flask-based web application that provides a user-friendly interface for common QIIME2 operations. It currently offers two main tools and likely won't see many additions beyond them:

1. **Artifact Export Tool**: Export QIIME2 artifacts (.qza) and visualizations (.qzv) to their native formats
2. **Metadata Validator**: Validate metadata files for use with QIIME2

## Application Structure

### Directory Structure

```
qiime2-go/
├── app.py                 # Main Flask application
├── requirements.txt       # Python dependencies
├── Dockerfile             # Docker configuration
├── docker-compose.yml     # Docker Compose configuration
├── static/                # Static assets
│   └── img/               # Images including logo
├── templates/             # HTML templates
│   ├── index.html         # Artifact Export Tool page
│   ├── artifact_types.html # Information about artifact types
│   └── metadata_validator.html # Metadata Validator page
├── uploads/               # Temporary storage for uploaded files
└── exports/               # Storage for exported artifacts
```

### Core Components

#### 1. Flask Application (`app.py`)

The main application file contains:

- Flask application setup and configuration
- Route definitions for different pages and API endpoints
- Helper functions for processing QIIME2 artifacts and metadata
- File handling logic for uploads and exports

#### 2. Templates

- **index.html**: The main page for the Artifact Export Tool
- **artifact_types.html**: Information about different QIIME2 artifact types and their export formats
- **metadata_validator.html**: Interface for validating QIIME2 metadata files

#### 3. Static Assets

- CSS styles (loaded from CDN)
- JavaScript for client-side functionality
- Images and icons

## Detailed Code Documentation

### Flask Application (`app.py`)

```python
"""
app.py - Flask application for QIIME2-go platform
"""
```

#### Configuration

```python
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
```

The application is configured with:
- A random secret key for session management
- Upload and export directories for file handling
- Allowed file extensions for uploads
- Maximum upload size (500MB)

#### Helper Functions

##### `allowed_file(filename, allowed_types=None)`

Checks if a file has an allowed extension.

```python
def allowed_file(filename, allowed_types=None):
    if allowed_types is None:
        allowed_types = ALLOWED_EXTENSIONS
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in allowed_types
```

##### `clean_old_files()`

Placeholder function for removing old files (not currently implemented).

```python
def clean_old_files():
    """Remove files older than 1 hour"""
    # Implementation here if needed
    pass
```

##### `get_artifact_type(file_path)`

Determines the type of a QIIME2 artifact.

```python
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
```

This function:
1. Attempts to load the file as a QIIME2 Artifact
2. If that fails, attempts to load it as a QIIME2 Visualization
3. Returns "Unknown" if neither attempt succeeds

##### `export_artifact(file_path, output_dir)`

Exports a QIIME2 artifact to its native format.

```python
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
```

This function:
1. Determines the artifact type
2. Uses the QIIME2 command-line tool to export the artifact
3. Returns the artifact type, output directory, and any error messages

##### `create_zip(directory)`

Creates a zip file of the exported data.

```python
def create_zip(directory):
    """Create a zip file of the exported data"""
    output_filename = os.path.join(app.config['EXPORT_FOLDER'], f"export_{uuid.uuid4().hex}.zip")
    shutil.make_archive(output_filename[:-4], 'zip', directory)
    return output_filename
```

This function:
1. Generates a unique filename for the zip file
2. Creates a zip archive of the specified directory
3. Returns the path to the created zip file

##### `validate_metadata(file_path)`

Validates a QIIME2 metadata file.

```python
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
```

This function performs several checks on a metadata file:
1. Checks for the presence of a `#q2:types` directive
2. Verifies that the file is a valid TSV
3. Checks for required ID columns
4. Checks for empty cells in the ID column
5. Checks for empty cells in other columns
6. Checks for duplicate IDs
7. Checks for invalid characters in column names

It returns:
- A boolean indicating whether the file is valid
- A list of errors (if any)
- A list of warnings (if any)

#### Routes

##### Main Page (`/`)

```python
@app.route('/')
def index():
    return render_template('index.html', active_tab='export')
```

Renders the main page with the Artifact Export Tool.

##### Metadata Validator Page (`/metadata-validator`)

```python
@app.route('/metadata-validator')
def metadata_validator():
    return render_template('metadata_validator.html', active_tab='metadata')
```

Renders the Metadata Validator page.

##### Artifact Types Page (`/artifact-types`)

```python
@app.route('/artifact-types')
def artifact_types():
    """Display information about QIIME2 artifact types and their exports"""
    return render_template('artifact_types.html', active_tab='export')
```

Renders a page with information about different QIIME2 artifact types.

##### Upload Endpoint (`/upload`)

```python
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
```

This route handles file uploads for the Artifact Export Tool:
1. Validates the uploaded file
2. Saves the file to the upload directory
3. Creates a temporary directory for export
4. Exports the artifact using the QIIME2 command-line tool
5. Creates a zip file of the exported data
6. Cleans up temporary files
7. Sends the zip file to the user for download

##### Metadata Validation Endpoint (`/validate-metadata`)

```python
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
```

This route handles metadata validation:
1. Validates the uploaded file
2. Saves the file to the upload directory
3. Validates the metadata file using the `validate_metadata` function
4. Cleans up temporary files
5. Returns a JSON response with validation results

#### Main Entry Point

```python
if __name__ == '__main__':
    # Clean old files on startup
    clean_old_files()
    app.run(debug=True)
```

Starts the Flask development server with debugging enabled.

## Frontend Components

### Common Elements

All pages share:
- A navigation bar with links to the different tools
- A consistent design with Bootstrap styling
- Responsive layout for different screen sizes
- Footer with information about the application

### Artifact Export Tool (`index.html`)

The main page features:
- A drag-and-drop file upload area
- Information about supported artifact types
- A link to the Artifact Types page for more information

### Metadata Validator (`metadata_validator.html`)

This page includes:
- A drag-and-drop file upload area
- A results section that displays validation errors and warnings
- Information about QIIME2 metadata requirements
- An example metadata file

### Artifact Types (`artifact_types.html`)

This page provides:
- Information about different QIIME2 artifact types
- Export formats for each artifact type
- Example commands for exporting artifacts using the QIIME2 command-line tool

## JavaScript Functionality

Each page includes JavaScript for:
- Handling drag-and-drop file uploads
- Displaying file information
- Form submission and AJAX requests
- Displaying validation results

## Dependencies

The application requires:
- Python 3.8+
- Flask
- QIIME2
- pandas
- Other Python packages listed in `requirements.txt`

## Docker Support

The application includes Docker configuration for easy deployment:
- `Dockerfile` for building a Docker image
- `docker-compose.yml` for running the application with Docker Compose

## Installation and Usage

### Local Installation

1. Clone the repository
2. Install the required Python packages: `pip install -r requirements.txt`
3. Ensure QIIME2 is installed and accessible
4. Run the application: `python app.py`
5. Open a web browser and navigate to `http://127.0.0.1:5000`

### Docker Installation

1. Clone the repository
2. Build and run the Docker container: `docker-compose up -d`
3. Open a web browser and navigate to `http://localhost:5000`