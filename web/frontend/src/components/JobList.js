import React from 'react';
import styled from 'styled-components';

const Container = styled.div`
  background: #2c2c2c;
  border-radius: 8px;
  padding: 15px;
  max-height: 300px;
  overflow-y: auto;
`;

const Title = styled.h3`
  margin: 0 0 15px 0;
  font-size: 16px;
  color: #fff;
`;

const JobItem = styled.div`
  padding: 12px;
  margin-bottom: 8px;
  background: ${props => props.selected ? '#00d4ff33' : '#333'};
  border: 1px solid ${props => props.selected ? '#00d4ff' : '#444'};
  border-radius: 4px;
  cursor: pointer;
  transition: all 0.2s;
  
  &:hover {
    border-color: #00d4ff;
  }
`;

const JobHeader = styled.div`
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 5px;
`;

const JobId = styled.span`
  font-size: 12px;
  color: #888;
`;

const StatusBadge = styled.span`
  font-size: 11px;
  padding: 2px 8px;
  border-radius: 12px;
  background: ${props => {
    switch (props.status) {
      case 'complete': return '#00d4ff33';
      case 'failed': return '#ff444433';
      case 'manual_review': return '#ffaa0033';
      default: return '#666';
    }
  }};
  color: ${props => {
    switch (props.status) {
      case 'complete': return '#00d4ff';
      case 'failed': return '#ff4444';
      case 'manual_review': return '#ffaa00';
      default: return '#aaa';
    }
  }};
`;

const JobInfo = styled.div`
  font-size: 12px;
  color: #888;
  
  p {
    margin: 2px 0;
  }
`;

const EmptyState = styled.p`
  text-align: center;
  color: #666;
  padding: 20px;
`;

function formatDate(dateString) {
  if (!dateString) return '';
  const date = new Date(dateString);
  return date.toLocaleString();
}

export default function JobList({ jobs, selectedJob, onSelectJob }) {
  if (jobs.length === 0) {
    return (
      <Container>
        <Title>Recent Jobs</Title>
        <EmptyState>No jobs yet. Upload an STL to get started.</EmptyState>
      </Container>
    );
  }
  
  return (
    <Container>
      <Title>Recent Jobs ({jobs.length})</Title>
      
      {jobs.map(job => (
        <JobItem
          key={job.id}
          selected={selectedJob?.id === job.id}
          onClick={() => onSelectJob(job)}
        >
          <JobHeader>
            <JobId>{job.id?.slice(0, 8)}...</JobId>
            <StatusBadge status={job.status}>{job.status}</StatusBadge>
          </JobHeader>
          
          <JobInfo>
            <p>{formatDate(job.created_at)}</p>
            {job.global_confidence && (
              <p>Confidence: {(job.global_confidence * 100).toFixed(0)}%</p>
            )}
            {job.final_iou && (
              <p>IoU: {(job.final_iou * 100).toFixed(0)}%</p>
            )}
          </JobInfo>
        </JobItem>
      ))}
    </Container>
  );
}
