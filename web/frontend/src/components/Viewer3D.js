import React, { Suspense } from 'react';
import { Canvas } from '@react-three/fiber';
import { OrbitControls, Grid, Box, Sphere } from '@react-three/drei';
import styled from 'styled-components';

const ViewerContainer = styled.div`
  height: 500px;
  background: #222;
  border-radius: 8px;
  overflow: hidden;
`;

const Info = styled.div`
  position: absolute;
  top: 10px;
  left: 10px;
  background: rgba(0, 0, 0, 0.7);
  padding: 10px;
  border-radius: 4px;
  font-size: 12px;
  
  p {
    margin: 2px 0;
  }
`;

// Placeholder mesh component
function MeshPlaceholder({ type }) {
  if (type === 'cylinder') {
    return (
      <mesh>
        <cylinderGeometry args={[1, 1, 2, 32]} />
        <meshStandardMaterial color="#00d4ff" wireframe />
      </mesh>
    );
  }
  
  return (
    <Box args={[2, 2, 2]}>
      <meshStandardMaterial color="#00d4ff" wireframe />
    </Box>
  );
}

function Scene({ job }) {
  // This would load the actual STL file in production
  // For now, show a placeholder based on detected zones
  
  return (
    <>
      <ambientLight intensity={0.5} />
      <pointLight position={[10, 10, 10]} />
      <Grid infiniteGrid fadeDistance={50} fadeStrength={1} />
      
      <MeshPlaceholder type="cylinder" />
      
      <OrbitControls enablePan={true} enableZoom={true} enableRotate={true} />
    </>
  );
}

export default function Viewer3D({ job }) {
  return (
    <ViewerContainer style={{ position: 'relative' }}>
      <Canvas camera={{ position: [5, 5, 5], fov: 50 }}>
        <Suspense fallback={null}>
          <Scene job={job} />
        </Suspense>
      </Canvas>
      
      <Info>
        <p><strong>Job ID:</strong> {job.id?.slice(0, 8)}...</p>
        <p><strong>Status:</strong> {job.status}</p>
        {job.global_confidence && (
          <p><strong>Confidence:</strong> {(job.global_confidence * 100).toFixed(1)}%</p>
        )}
        {job.final_iou && (
          <p><strong>IoU:</strong> {(job.final_iou * 100).toFixed(1)}%</p>
        )}
      </Info>
    </ViewerContainer>
  );
}
