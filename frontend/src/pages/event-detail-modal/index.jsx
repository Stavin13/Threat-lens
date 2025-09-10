import React, { useState, useEffect } from 'react';
import { useSearchParams, useNavigate } from 'react-router-dom';
import NavigationHeader from '../../components/ui/NavigationHeader';
import EventHeader from './components/EventHeader';
import EventInformation from './components/EventInformation';
import AIAnalysis from './components/AIAnalysis';
import RawLogData from './components/RawLogData';
import EventActions from './components/EventActions';
import Icon from '../../components/AppIcon';


const EventDetailModal = () => {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const [activeTab, setActiveTab] = useState('information');
  const [currentEventIndex, setCurrentEventIndex] = useState(0);
  const [loading, setLoading] = useState(false);

  const eventId = searchParams?.get('id');

  // Mock events data
  const mockEvents = [
    {
      id: "EVT-2025-001234",
      timestamp: "2025-01-08T05:15:23.456Z",
      source: "web-server-01.prod.threatlens.com",
      message: "Multiple failed authentication attempts detected from IP 192.168.1.100. User account \'admin\' attempted login 15 times within 5 minutes. Account temporarily locked for security.",
      category: "Authentication",
      severity: 8,
      status: "investigating",
      userAgent: "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
      ipAddress: "192.168.1.100",
      markedForFollowUp: true,
      priority: "High",
      assignedTo: "Sarah Chen",
      lastModified: "2025-01-08T05:20:15.789Z",
      parsed: true,
      logFormat: "JSON",
      encoding: "UTF-8",
      rawLog: `{
  "timestamp": "2025-01-08T05:15:23.456Z",
  "level": "WARN",
  "source": "auth-service",
  "event_type": "authentication_failure",
  "user": "admin",
  "ip_address": "192.168.1.100",
  "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
  "attempt_count": 15,
  "time_window": "5m",
  "action_taken": "account_locked",
  "session_id": "sess_abc123def456",
  "request_id": "req_789xyz012",
  "geo_location": {
    "country": "US",
    "region": "California",
    "city": "San Francisco"
  },
  "threat_indicators": [
    "brute_force_pattern",
    "suspicious_timing",
    "known_attack_vector"
  ]
}`,
      parsingDetails: {
        parser: "JSON Parser v2.1",
        fieldsExtracted: 12,
        parseTime: 45,
        confidence: 98,
        warnings: ["Unusual user agent pattern detected"]
      },
      metadata: {
        correlationId: "CORR-2025-5678",
        ruleTriggered: "AUTH-BRUTE-FORCE-001",
        dataSource: "Nginx Access Logs",
        ingestionTime: "2025-01-08T05:15:25.123Z"
      }
    },
    {
      id: "EVT-2025-001235",
      timestamp: "2025-01-08T05:18:45.789Z",
      source: "firewall-01.prod.threatlens.com",
      message: "Suspicious network traffic detected. Outbound connection to known malicious IP 203.0.113.45 blocked. Protocol: TCP, Port: 443, Data transferred: 2.3MB before block.",
      category: "Network",
      severity: 9,
      status: "open",
      ipAddress: "203.0.113.45",
      priority: "Critical",
      lastModified: "2025-01-08T05:18:45.789Z",
      parsed: true,
      logFormat: "Syslog",
      encoding: "UTF-8",
      rawLog: `Jan  8 05:18:45 firewall-01 kernel: [12345.678901] THREAT-BLOCK: IN= OUT=eth0 SRC=10.0.1.50 DST=203.0.113.45 LEN=1500 TOS=0x00 PREC=0x00 TTL=64 ID=54321 DF PROTO=TCP SPT=54321 DPT=443 WINDOW=65535 RES=0x00 ACK PSH URGP=0
Jan  8 05:18:45 firewall-01 threat-engine: MALICIOUS_IP_DETECTED src=10.0.1.50 dst=203.0.113.45 threat_score=95 category=C2_COMMUNICATION action=BLOCK bytes_transferred=2415616
Jan  8 05:18:45 firewall-01 threat-engine: CORRELATION_ALERT event_id=EVT-2025-001235 related_events=[EVT-2025-001230,EVT-2025-001232] confidence=HIGH`,
      parsingDetails: {
        parser: "Syslog Parser v1.8",
        fieldsExtracted: 18,
        parseTime: 32,
        confidence: 95,
        warnings: []
      }
    }
  ];

  // Mock AI analysis data
  const mockAIAnalysis = {
    "EVT-2025-001234": {
      aiSeverity: 8,
      confidence: 92,
      riskScore: 85,
      threatCategory: "Brute Force Attack",
      explanation: "This event represents a classic brute force authentication attack pattern. The AI analysis identified multiple indicators consistent with automated credential stuffing attempts, including rapid successive login failures, consistent timing patterns, and targeting of privileged accounts. The attack originated from a single IP address and focused on the 'admin' account, which is a common target for attackers seeking elevated privileges.",
      indicators: [
        {
          type: "Rapid Authentication Failures",
          description: "15 failed login attempts within 5 minutes exceeds normal user behavior",
          severity: 8
        },
        {
          type: "Privileged Account Targeting",
          description: "Attack focused on \'admin\' account with elevated system privileges",
          severity: 7
        },
        {
          type: "Consistent Timing Pattern",
          description: "Regular intervals between attempts suggest automated tooling",
          severity: 6
        },
        {
          type: "Single Source IP",
          description: "All attempts originated from 192.168.1.100",
          severity: 5
        }
      ],
      recommendations: [
        {
          action: "Implement Account Lockout Policy",
          description: "Configure progressive lockout delays after failed authentication attempts",
          priority: "High",
          estimatedTime: "30 minutes"
        },
        {
          action: "Enable Multi-Factor Authentication",
          description: "Require additional authentication factors for privileged accounts",
          priority: "High",
          estimatedTime: "2 hours"
        },
        {
          action: "IP Address Investigation",
          description: "Investigate source IP 192.168.1.100 for additional malicious activity",
          priority: "Medium",
          estimatedTime: "1 hour"
        },
        {
          action: "Monitor Related Accounts",
          description: "Increase monitoring for other privileged accounts for similar attack patterns",
          priority: "Medium",
          estimatedTime: "15 minutes"
        }
      ],
      mitreMapping: [
        {
          id: "T1110.001",
          technique: "Brute Force: Password Guessing",
          description: "Adversaries may use brute force techniques to gain access to accounts when passwords are unknown"
        },
        {
          id: "T1078.003",
          technique: "Valid Accounts: Local Accounts",
          description: "Adversaries may obtain and abuse credentials of a local account as a means of gaining Initial Access"
        }
      ]
    },
    "EVT-2025-001235": {
      aiSeverity: 9,
      confidence: 96,
      riskScore: 94,
      threatCategory: "Command & Control",
      explanation: "This event indicates a potential command and control (C2) communication attempt. The AI analysis detected an outbound connection to a known malicious IP address associated with advanced persistent threat (APT) groups. The substantial data transfer (2.3MB) before blocking suggests potential data exfiltration or malware communication. This represents a critical security incident requiring immediate investigation.",
      indicators: [
        {
          type: "Known Malicious IP",
          description: "Destination IP 203.0.113.45 is listed in threat intelligence feeds",
          severity: 9
        },
        {
          type: "Substantial Data Transfer",
          description: "2.3MB of data transferred before connection was blocked",
          severity: 8
        },
        {
          type: "Encrypted Communication",
          description: "Connection attempted over HTTPS (port 443) to hide payload",
          severity: 7
        },
        {
          type: "Internal Host Compromise",
          description: "Communication originated from internal network segment",
          severity: 8
        }
      ],
      recommendations: [
        {
          action: "Immediate Host Isolation",
          description: "Isolate source host 10.0.1.50 from network to prevent lateral movement",
          priority: "Critical",
          estimatedTime: "5 minutes"
        },
        {
          action: "Forensic Analysis",
          description: "Conduct full forensic imaging and analysis of compromised host",
          priority: "High",
          estimatedTime: "4 hours"
        },
        {
          action: "Network Traffic Analysis",
          description: "Analyze historical network logs for previous communications to this IP",
          priority: "High",
          estimatedTime: "2 hours"
        },
        {
          action: "Threat Intelligence Correlation",
          description: "Cross-reference with threat intelligence for related IOCs and TTPs",
          priority: "Medium",
          estimatedTime: "1 hour"
        }
      ],
      mitreMapping: [
        {
          id: "T1071.001",
          technique: "Application Layer Protocol: Web Protocols",
          description: "Adversaries may communicate using application layer protocols to avoid detection"
        },
        {
          id: "T1041",
          technique: "Exfiltration Over C2 Channel",
          description: "Adversaries may steal data by exfiltrating it over an existing command and control channel"
        }
      ]
    }
  };

  const currentEvent = mockEvents?.find(event => event?.id === eventId) || mockEvents?.[0];
  const currentAnalysis = mockAIAnalysis?.[currentEvent?.id];

  useEffect(() => {
    if (eventId) {
      const index = mockEvents?.findIndex(event => event?.id === eventId);
      setCurrentEventIndex(index >= 0 ? index : 0);
    }
  }, [eventId]);

  const handleClose = () => {
    navigate('/events-management');
  };

  const handlePrevious = () => {
    if (currentEventIndex > 0) {
      const prevEvent = mockEvents?.[currentEventIndex - 1];
      navigate(`/event-detail-modal?id=${prevEvent?.id}`);
    }
  };

  const handleNext = () => {
    if (currentEventIndex < mockEvents?.length - 1) {
      const nextEvent = mockEvents?.[currentEventIndex + 1];
      navigate(`/event-detail-modal?id=${nextEvent?.id}`);
    }
  };

  const handleMarkForFollowUp = async (eventId, marked) => {
    setLoading(true);
    // Simulate API call
    await new Promise(resolve => setTimeout(resolve, 500));
    console.log(`Event ${eventId} marked for follow-up: ${marked}`);
    setLoading(false);
  };

  const handleExportReport = async (eventId) => {
    // Simulate report generation
    await new Promise(resolve => setTimeout(resolve, 1000));
    
    const reportData = {
      event: currentEvent,
      analysis: currentAnalysis,
      generatedAt: new Date()?.toISOString(),
      analyst: "System Generated"
    };
    
    const blob = new Blob([JSON.stringify(reportData, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `threat-analysis-report-${eventId}.json`;
    document.body?.appendChild(a);
    a?.click();
    document.body?.removeChild(a);
    URL.revokeObjectURL(url);
  };

  const handleCopyEventData = async (event) => {
    const eventData = {
      id: event?.id,
      timestamp: event?.timestamp,
      source: event?.source,
      message: event?.message,
      category: event?.category,
      severity: event?.severity,
      analysis: currentAnalysis
    };
    
    await navigator.clipboard?.writeText(JSON.stringify(eventData, null, 2));
  };

  const tabs = [
    { id: 'information', label: 'Event Information', icon: 'Info' },
    { id: 'analysis', label: 'AI Analysis', icon: 'Brain' },
    { id: 'rawlog', label: 'Raw Log Data', icon: 'FileText' },
    { id: 'actions', label: 'Actions', icon: 'Settings' }
  ];

  return (
    <div className="min-h-screen bg-background">
      <NavigationHeader />
      {/* Modal Overlay */}
      <div className="fixed inset-0 z-50 bg-black/50 flex items-center justify-center p-4 pt-20">
        <div className="bg-card rounded-lg shadow-elevation-4 w-full max-w-6xl max-h-[90vh] flex flex-col">
          {/* Event Header */}
          <EventHeader
            event={currentEvent}
            onClose={handleClose}
            onPrevious={handlePrevious}
            onNext={handleNext}
            hasPrevious={currentEventIndex > 0}
            hasNext={currentEventIndex < mockEvents?.length - 1}
          />

          {/* Tab Navigation */}
          <div className="border-b border-border bg-muted/30">
            <div className="flex space-x-1 p-2">
              {tabs?.map((tab) => (
                <button
                  key={tab?.id}
                  onClick={() => setActiveTab(tab?.id)}
                  className={`flex items-center space-x-2 px-4 py-2 rounded-md text-sm font-medium transition-micro ${
                    activeTab === tab?.id
                      ? 'bg-primary text-primary-foreground shadow-elevation-2'
                      : 'text-muted-foreground hover:text-foreground hover:bg-muted'
                  }`}
                >
                  <Icon name={tab?.icon} size={16} />
                  <span className="hidden sm:inline">{tab?.label}</span>
                </button>
              ))}
            </div>
          </div>

          {/* Tab Content */}
          <div className="flex-1 overflow-auto p-6">
            {activeTab === 'information' && (
              <EventInformation event={currentEvent} />
            )}
            
            {activeTab === 'analysis' && (
              <AIAnalysis event={currentEvent} analysis={currentAnalysis} />
            )}
            
            {activeTab === 'rawlog' && (
              <RawLogData event={currentEvent} />
            )}
            
            {activeTab === 'actions' && (
              <EventActions
                event={currentEvent}
                onMarkForFollowUp={handleMarkForFollowUp}
                onExportReport={handleExportReport}
                onCopyEventData={handleCopyEventData}
              />
            )}
          </div>
        </div>
      </div>
    </div>
  );
};

export default EventDetailModal;