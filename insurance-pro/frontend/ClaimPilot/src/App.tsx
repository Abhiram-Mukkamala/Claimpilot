import { AppRoutes } from './routes/AppRoutes';
import { DottedWaveBackground } from './components/ui/DottedWaveBackground';

function App() {
  return (
    <div className="claimpilot-app-root" style={{ position: 'relative', minHeight: '100vh', backgroundColor: '#070709' }}>
      <DottedWaveBackground />
      <div className="claimpilot-app-content" style={{ position: 'relative', zIndex: 1, minHeight: '100vh' }}>
        <AppRoutes />
      </div>
    </div>
  );
}

export default App;
