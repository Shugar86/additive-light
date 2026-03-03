import React, { useState, useCallback } from 'react';
import { useDropzone } from 'react-dropzone';
import styled from 'styled-components';
import axios from 'axios';
import Viewer3D from './components/Viewer3D';
import JobList from './components/JobList';
import ProgressPanel from './components/ProgressPanel';

const Container = styled.div`
  display: flex;
  flex-direction: column;
  min-height: 100vh;
`;

const Header = styled.header`
  background: #2c2c2c;
  padding: 20px;
  border-bottom: 1px solid #444;
  
  h1 {
    margin: 0;
    font-size: 24px;
    color: #00d4ff;
  }
  
  p {
    margin: 5px 0 0 0;
    color: #888;
    font-size: 14px;
  }
`;

const Main = styled.main`
  display: flex;
  flex: 1;
  padding: 20px;
  gap: 20px;
`;

const LeftPanel = styled.div`
  width: 400px;
  display: flex;
  flex-direction: column;
  gap: 20px;
`;

const RightPanel = styled.div`
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 20px;
`;

const Dropzone = styled.div`
  border: 2px dashed #666;
  border-radius: 8px;
  padding: 40px 20px;
  text-align: center;
  cursor: pointer;
  transition: all 0.2s;
  
  &:hover {
    border-color: #00d4ff;
    background: rgba(0, 212, 255, 0.05);
  }
  
  &.active {
    border-color: #00d4ff;
    background: rgba(0, 212, 255, 0.1);
  }
  
  p {
    margin: 0;
    color: #888;
  }
`;

const Button = styled.button`
  background: #00d4ff;
  color: #000;
  border: none;
  padding: 12px 24px;
  border-radius: 4px;
  font-size: 16px;
  font-weight: bold;
  cursor: pointer;
  transition: all 0.2s;
  
  &:hover {
    background: #33ddff;
  }
  
  &:disabled {
    background: #444;
    color: #666;
    cursor: not-allowed;
  }
`;

const Select = styled.select`
  background: #333;
  color: #fff;
  border: 1px solid #555;
  padding: 10px;
  border-radius: 4px;
  font-size: 14px;
  width: 100%;
  
  &:focus {
    outline: none;
    border-color: #00d4ff;
  }
`;

const Label = styled.label`
  display: block;
  margin-bottom: 8px;
  color: #aaa;
  font-size: 14px;
`;

const FormGroup = styled.div`
  margin-bottom: 15px;
`;

function App() {
  const [uploadedFile, setUploadedFile] = useState(null);
  const [uploading, setUploading] = useState(false);
  const [jobs, setJobs] = useState([]);
  const [selectedJob, setSelectedJob] = useState(null);
  const [settings, setSettings] = useState({
    baseAxis: 'Z',
    confidenceThreshold: 0.7
  });

  const onDrop = useCallback(async (acceptedFiles) => {
    if (acceptedFiles.length === 0) return;
    
    const file = acceptedFiles[0];
    if (!file.name.endsWith('.stl')) {
      alert('Only STL files are supported');
      return;
    }
    
    setUploading(true);
    
    try {
      const formData = new FormData();
      formData.append('file', file);
      
      const response = await axios.post('/api/v1/upload', formData, {
        headers: {
          'Content-Type': 'multipart/form-data'
        }
      });
      
      setUploadedFile({
        ...response.data,
        originalName: file.name
      });
    } catch (error) {
      alert('Upload failed: ' + error.message);
    } finally {
      setUploading(false);
    }
  }, []);

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: { 'model/stl': ['.stl'] },
    multiple: false
  });

  const startProcessing = async () => {
    if (!uploadedFile) return;
    
    try {
      const jobData = {
        source_stl: `uploads/${uploadedFile.file_id}_${uploadedFile.filename}`,
        base_axis: settings.baseAxis,
        confidence_threshold: settings.confidenceThreshold
      };
      
      const response = await axios.post('/api/v1/jobs', jobData);
      
      setJobs([response.data, ...jobs]);
      setUploadedFile(null);
    } catch (error) {
      alert('Failed to create job: ' + error.message);
    }
  };

  return (
    <Container>
      <Header>
        <h1>Generative Design Intelligence</h1>
        <p>3D Scan → Parametric CAD → G-code</p>
      </Header>
      
      <Main>
        <LeftPanel>
          <div>
            <h3>Upload STL</h3>
            <Dropzone
              {...getRootProps()}
              className={isDragActive ? 'active' : ''}
            >
              <input {...getInputProps()} />
              {uploading ? (
                <p>Uploading...</p>
              ) : uploadedFile ? (
                <p>✓ {uploadedFile.originalName}</p>
              ) : (
                <>
                  <p>Drag & drop an STL file here</p>
                  <p>or click to select</p>
                </>
              )}
            </Dropzone>
          </div>
          
          {uploadedFile && (
            <div>
              <h3>Settings</h3>
              
              <FormGroup>
                <Label>Build Axis</Label>
                <Select
                  value={settings.baseAxis}
                  onChange={(e) => setSettings({...settings, baseAxis: e.target.value})}
                >
                  <option value="Z">Z (vertical)</option>
                  <option value="Y">Y</option>
                  <option value="X">X</option>
                </Select>
              </FormGroup>
              
              <FormGroup>
                <Label>Confidence Threshold: {settings.confidenceThreshold}</Label>
                <input
                  type="range"
                  min="0.5"
                  max="0.95"
                  step="0.05"
                  value={settings.confidenceThreshold}
                  onChange={(e) => setSettings({...settings, confidenceThreshold: parseFloat(e.target.value)})}
                  style={{ width: '100%' }}
                />
              </FormGroup>
              
              <Button onClick={startProcessing}>
                ▶ Start Processing
              </Button>
            </div>
          )}
          
          <JobList
            jobs={jobs}
            selectedJob={selectedJob}
            onSelectJob={setSelectedJob}
          />
        </LeftPanel>
        
        <RightPanel>
          {selectedJob ? (
            <>
              <Viewer3D job={selectedJob} />
              <ProgressPanel job={selectedJob} />
            </>
          ) : (
            <div style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              height: '100%',
              color: '#666'
            }}>
              <p>Select a job to view 3D preview and progress</p>
            </div>
          )}
        </RightPanel>
      </Main>
    </Container>
  );
}

export default App;
