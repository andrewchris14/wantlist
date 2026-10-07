import React from 'react';
import {createRoot} from 'react-dom/client';
import OwnerApp from './OwnerApp.jsx';
import '../site/styles.css';
import './styles.css';
createRoot(document.getElementById('root')).render(<OwnerApp/>);
