import React, { useEffect, useState } from 'react';
import styled from 'styled-components';

const Container = styled.div`
  background: #2c2c2c;
  border-radius: 8px;
  padding: 20px;
`;

const Title = styled.h3`
  margin: 0 0 20px 0;
  font-size: 16px;
  color: #fff;
`;

const ProgressBar = styled.div`
  width: 100%;
  height: 30px;
  background: #333;
  border-radius: 4px;
  overflow: hidden;
  position: relative;
`;

const ProgressFill = styled.div`
  height: 100%;
  background: linear-gradient(90deg, #00d4ff, #00a8cc);
  width: ${props => props.percent};
  transition: width 0.3s ease;
  display: flex;
  align-items: center;
  justify-content: flex-end;
  padding-right: 10px;
`;

const ProgressText = styled.span`
  font-size: 12px;
  color: #000;
  font-weight: bold;
`;

const LogContainer = styled.div`
  margin-top: 20px;
  background: #1a1a1a;
  border-radius: 4px;
  padding: 15px;
  font-family: 'Courier New', monospace;
  font-size: 12px;
  max-height: 200px;
  overflow-y: auto;
`;

const LogEntry = styled.div`
  color: ${props => {
    if (props.type === 'error') return '#ff4444';
    if (props.type === 'success') return '#00ff00';
    return '#888';
  }};
  margin: 3px 0;
`;

const PhaseGrid = styled.div`
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 10px;
  margin-top: 20px;
`;

const Phase = styled.div`
  padding: 10px;
  background: ${props => props.active ? '#00d4ff33' : '#333'};
  border: 1px solid ${props => props.active ? '#00d4ff' : '#444'};
  border-radius: 4px;
  text-align: center;
  font-size: 12px;
  
  .name {
    color: ${props => props.active ? '#00d4ff' : '#888'};
    font-weight: ${props => props.active ? 'bold' : 'normal'};
  }
  
  .status {
    color: #666;
    font-size: 10px;
    margin-top: 4px;
  }
`;

// Mock logs for demo
const MOCK_LOGS = [
  { message: 'Loading STL file...', type: 'info' },
  { message: 'STL loaded: 68405 bytes', type: 'info' },
  { message: 'Slicing mesh (step=0.1mm)...', type: 'info' },
  { message: 'Generated 400 slices', type: 'success' },
  { message: 'Analyzing geometry...', type: 'info' },
  { message: 'Detected 1 zone (Cylinder)', type: 'success' },
  { message: 'Global confidence: 0.95', type: 'success' },
  { message: 'Sending to LLM for synthesis...', type: 'info' },
];

function getProgressPercent(status) {
  switch (status) {
    case 'pending': return 0;
    case 'processing': return 20;
    case 'sensor_complete': return 40;
    case 'synthesizing': return 60;
    case 'judge_complete': return 80;
    case 'optimizing': return 90;
    case 'complete': return 100;
    case 'failed': return 100;
    case 'manual_review': return 100;
    default: return 0;
  }
}

export default function ProgressPanel({ job }) {
  const [logs, setLogs] = useState(MOCK_LOGS);
  const progress = getProgressPercent(job.status);
  
  // In production, this would connect to WebSocket
  useEffect(() => {
    // WebSocket connection would go here
    // const ws = new WebSocket(`ws://localhost:8000/ws/jobs/${job.id}`);
  }, [job.id]);
  
  return (
    <Container>
      <Title>Processing Progress</Title>
      
      <ProgressBar>
        <ProgressFill percent={`${progress}%`}>
          {progress > 10 && <ProgressText>{progress}%</ProgressText>}
        </ProgressFill>
      </ProgressBar>
      
      <PhaseGrid>
        <Phase active={progress >= 20}>
          <div className="name">1. Sensor</div>
          <div className="status">{progress >= 40 ? '✓' : progress >= 20 ? '...' : ''}</div>
        </Phase>
        <Phase active={progress >= 40}>
          <div className="name">2. Approximator</div>
          <div className="status">{progress >= 50 ? '✓' : progress >= 40 ? '...' : ''}</div>
        </Phase>
        <Phase active={progress >= 60}>
          <div className="name">3. Synthesis</div>
          <div className="status">{progress >= 80 ? '✓' : progress >= 60 ? '...' : ''}</div>
        </Phase>
        <Phase active={progress >= 80}>
          <div className="name">4. Judge</div>
          <div className="status">{progress >= 100 ? '✓' : progress >= 80 ? '...' : ''}</div>
        </Phase>
      </PhaseGrid>
      
      <LogContainer>
        {logs.map((log, i) => (
          <LogEntry key={i} type={log.type}>
            [{new Date().toLocaleTimeString()}] {log.message}
          </LogEntry>
        ))}
        
        {job.status === 'complete' && (
          <LogEntry type="success">
            [{new Date().toLocaleTimeString()}] ✓ Pipeline complete!
          </LogEntry>
        )}
        
        {job.status === 'failed' && (
          <LogEntry type="error">
            [{new Date().toLocaleTimeString()}] ✗ Pipeline failed: {job.error_message}
          </LogEntry>
        )}
      </LogContainer>
    </Container>
  );
}
