"""
ThreatLens FastAPI Application

Main FastAPI application providing REST API endpoints for security log analysis.
Includes log ingestion, event retrieval, and automated processing capabilities.
"""
import logging
import os
import time
from contextlib import asynccontextmanager
from datetime import datetime, timezone, date
from typing import List, Optional, Dict, Any
from fastapi import FastAPI, HTTPException, Depends, UploadFile, File, Query, BackgroundTasks, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy import text, and_, or_, desc, asc

# Import error handling and logging
from app.logging_config import setup_logging, get_logger, set_correlation_id, generate_correlation_id
from app.error_handling import (
    global_exception_handler,
    http_exception_handler,
    validation_exception_handler,
    ThreatLensError
)
from app.middleware import (
    CorrelationIdMiddleware,
    RequestLoggingMiddleware,
    SecurityHeadersMiddleware,
    RateLimitMiddleware,
    InputValidationMiddleware,
    MetricsMiddleware,
    set_metrics_middleware
)
from app.health_endpoints import health_router

from app.database import (
    get_database_session, 
    init_database, 
    check_database_health,
    get_database_stats,
    close_database_connections
)
from app.models import RawLog, Event, AIAnalysis as AIAnalysisModel
from app.schemas import (
    IngestionRequest, 
    IngestionResponse, 
    EventResponse, 
    EventListResponse,
    EventFilters,
    AIAnalysis,
    HealthCheckResponse,
    ErrorResponse,
    ReportRequest,
    ReportResponse
)
from app.ingestion import ingest_log_file, ingest_log_text, IngestionError
from app.parser import parse_log_entries, ParsingError
from app.analyzer import analyze_event, AnalysisError
from app.report_generator import generate_daily_report, save_report_record
from app.scheduler import (
    start_scheduled_reports, 
    stop_scheduled_reports, 
    get_scheduler_status,
    get_audit_log,
    trigger_manual_report,
    get_report_files_info
)
from app.realtime.event_loop import realtime_manager
from app.realtime.config_manager import get_config_manager
from app.realtime.models import LogSourceConfig, LogSourceType, MonitoringStatus
from app.realtime.websocket_api import WebSocketAPI
from app.schemas import (
    LogSourceConfigRequest, LogSourceConfigResponse, 
    NotificationRuleRequest, NotificationRuleResponse,
    MonitoringConfigResponse, ProcessingMetricsResponse
)
from app.realtime.health_api import health_router

# Initialize comprehensive logging
setup_logging(
    log_level=os.getenv('LOG_LEVEL', 'INFO'),
    log_format=os.getenv('LOG_FORMAT', 'json'),
    log_file=os.getenv('LOG_FILE', 'logs/threatlens.log'),
    enable_console=True
)
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager for startup and shutdown events."""
    # Startup
    logger.info("Starting ThreatLens API server...")
    
    # Initialize database
    if not init_database():
        logger.error("Failed to initialize database")
        raise RuntimeError("Database initialization failed")
    
    logger.info("Database initialized successfully")
    
    # Start scheduled report generation
    try:
        start_scheduled_reports()
        logger.info("Scheduled report generation started")
    except Exception as e:
        logger.error(f"Failed to start scheduled reports: {str(e)}")
        # Don't fail startup if scheduler fails
    
    # Start real-time components
    try:
        await realtime_manager.start_all()
        logger.info("Real-time components started")
    except Exception as e:
        logger.error(f"Failed to start real-time components: {str(e)}")
        # Don't fail startup if real-time components fail
    
    # Start health monitoring
    try:
        from app.realtime.health_monitor import health_monitor
        from app.realtime.health_checks import register_all_health_checks
        
        # Register health checks for real-time components
        components = {
            'file_monitor': getattr(realtime_manager, 'file_monitor', None),
            'ingestion_queue': getattr(realtime_manager, 'ingestion_queue', None),
            'websocket_manager': getattr(realtime_manager, 'websocket_manager', None),
            'enhanced_processor': getattr(realtime_manager, 'enhanced_processor', None)
        }
        
        # Filter out None components
        available_components = {k: v for k, v in components.items() if v is not None}
        
        if available_components:
            register_all_health_checks(health_monitor, available_components)
            await health_monitor.start_monitoring()
            logger.info("Health monitoring started")
        else:
            logger.warning("No real-time components available for health monitoring")
            
    except Exception as e:
        logger.error(f"Failed to start health monitoring: {str(e)}")
        # Don't fail startup if health monitoring fails
    
    yield
    
    # Shutdown
    logger.info("Shutting down ThreatLens API server...")
    
    # Stop scheduled reports
    try:
        stop_scheduled_reports()
        logger.info("Scheduled report generation stopped")
    except Exception as e:
        logger.error(f"Error stopping scheduled reports: {str(e)}")
    
    # Stop real-time components
    try:
        await realtime_manager.stop_all()
        logger.info("Real-time components stopped")
    except Exception as e:
        logger.error(f"Error stopping real-time components: {str(e)}")
    
    # Stop health monitoring
    try:
        from app.realtime.health_monitor import health_monitor
        await health_monitor.stop_monitoring()
        logger.info("Health monitoring stopped")
    except Exception as e:
        logger.error(f"Error stopping health monitoring: {str(e)}")
    
    close_database_connections()


# Create FastAPI application
app = FastAPI(
    title="ThreatLens API",
    description="AI-powered security log analysis and threat detection system",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan
)

# Add error handlers
app.add_exception_handler(Exception, global_exception_handler)
app.add_exception_handler(HTTPException, http_exception_handler)
app.add_exception_handler(RequestValidationError, validation_exception_handler)

# Add middleware (order matters - first added is outermost)
app.add_middleware(SecurityHeadersMiddleware, strict_csp=False)  # Set to True for production
app.add_middleware(InputValidationMiddleware, max_request_size=50 * 1024 * 1024)
app.add_middleware(RateLimitMiddleware, requests_per_minute=120, burst_limit=10, block_duration=300)

# Create and add metrics middleware
metrics_middleware = MetricsMiddleware(app)
app.add_middleware(MetricsMiddleware)
set_metrics_middleware(metrics_middleware)

app.add_middleware(RequestLoggingMiddleware, log_body=False, max_body_size=1024)
app.add_middleware(CorrelationIdMiddleware)

# Configure CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],  # React dev server
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

# Include health monitoring router
app.include_router(health_router)

# Include real-time monitoring API router
from app.realtime.monitoring_api import monitoring_router
app.include_router(monitoring_router)

# Include authentication API router
from app.realtime.auth_api import auth_router
app.include_router(auth_router)


# Error handlers
@app.exception_handler(IngestionError)
async def ingestion_error_handler(request, exc: IngestionError):
    """Handle ingestion errors."""
    error_response = ErrorResponse(
        error="IngestionError",
        message=str(exc),
        timestamp=datetime.now(timezone.utc)
    )
    return JSONResponse(
        status_code=400,
        content=jsonable_encoder(error_response)
    )


@app.exception_handler(ParsingError)
async def parsing_error_handler(request, exc: ParsingError):
    """Handle parsing errors."""
    error_response = ErrorResponse(
        error="ParsingError", 
        message=str(exc),
        timestamp=datetime.now(timezone.utc)
    )
    return JSONResponse(
        status_code=422,
        content=jsonable_encoder(error_response)
    )


@app.exception_handler(AnalysisError)
async def analysis_error_handler(request, exc: AnalysisError):
    """Handle analysis errors."""
    error_response = ErrorResponse(
        error="AnalysisError",
        message=str(exc),
        timestamp=datetime.now(timezone.utc)
    )
    return JSONResponse(
        status_code=500,
        content=jsonable_encoder(error_response)
    )


# Import background task system
from app.background_tasks import process_raw_log, get_processing_stats


# API Endpoints

@app.get("/", response_model=Dict[str, str])
async def root():
    """Root endpoint with API information."""
    return {
        "name": "ThreatLens API",
        "version": "1.0.0",
        "description": "AI-powered security log analysis system",
        "docs": "/docs"
    }


# Simple health check for Docker
@app.get("/health-simple")
async def health_check_simple():
    """Simple health check endpoint for Docker health checks."""
    try:
        # Just check if the database connection works
        db_health = check_database_health()
        return {
            "status": "healthy" if db_health["status"] == "healthy" else "unhealthy",
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
    except Exception as e:
        return {
            "status": "unhealthy",
            "error": str(e),
            "timestamp": datetime.now(timezone.utc).isoformat()
        }

@app.get("/health", response_model=HealthCheckResponse)
async def health_check():
    """Health check endpoint for monitoring system status."""
    try:
        db_health = check_database_health()
        
        # Try to get realtime health, but don't fail if it has issues
        try:
            realtime_health = await realtime_manager.health_check()
        except Exception as e:
            realtime_health = {
                "overall_status": "degraded",
                "error": str(e),
                "components": {}
            }
        
        overall_status = "healthy"
        if db_health["status"] != "healthy":
            overall_status = "unhealthy"
        elif realtime_health["overall_status"] != "healthy":
            overall_status = "degraded"
        
        return HealthCheckResponse(
            status=overall_status,
            database=db_health,
            realtime=realtime_health,
            timestamp=datetime.now(timezone.utc)
        )
    except Exception as e:
        return HealthCheckResponse(
            status="unhealthy",
            database={"status": "unknown", "error": str(e)},
            realtime={"overall_status": "unknown", "error": str(e)},
            timestamp=datetime.now(timezone.utc)
        )


@app.post("/ingest-log", response_model=IngestionResponse)
async def ingest_log_endpoint(
    background_tasks: BackgroundTasks,
    file: Optional[UploadFile] = File(None),
    content: Optional[str] = None,
    source: Optional[str] = None
):
    """
    Ingest log data from file upload or text input.
    
    Args:
        background_tasks: FastAPI background tasks
        file: Optional uploaded log file
        content: Optional log content as text
        source: Optional source identifier
        
    Returns:
        IngestionResponse with ingestion details
        
    Raises:
        HTTPException: If ingestion fails or invalid input provided
    """
    if file and content:
        raise HTTPException(
            status_code=400,
            detail="Cannot provide both file and content. Choose one method."
        )
    
    if not file and not content:
        raise HTTPException(
            status_code=400,
            detail="Must provide either file or content for ingestion."
        )
    
    try:
        # Handle file upload
        if file:
            response = await ingest_log_file(file, source)
        else:
            # Handle text input
            if not source:
                source = "text_input"
            
            request = IngestionRequest(content=content, source=source)
            response = ingest_log_text(request)
        
        # Trigger background processing with enhanced error handling
        background_tasks.add_task(process_raw_log, response.raw_log_id)
        
        logger.info(f"Log ingestion successful: {response.raw_log_id}")
        return response
        
    except IngestionError:
        raise
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error in log ingestion: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Ingestion failed: {str(e)}")


@app.get("/events", response_model=EventListResponse)
async def get_events(
    page: int = Query(1, ge=1, description="Page number"),
    per_page: int = Query(20, ge=1, le=100, description="Events per page"),
    category: Optional[str] = Query(None, description="Filter by event category"),
    min_severity: Optional[int] = Query(None, ge=1, le=10, description="Minimum severity score"),
    max_severity: Optional[int] = Query(None, ge=1, le=10, description="Maximum severity score"),
    start_date: Optional[datetime] = Query(None, description="Start date for filtering"),
    end_date: Optional[datetime] = Query(None, description="End date for filtering"),
    source: Optional[str] = Query(None, description="Filter by source"),
    sort_by: str = Query("timestamp", description="Sort field (timestamp, severity, source, category)"),
    sort_order: str = Query("desc", description="Sort order (asc, desc)"),
    db: Session = Depends(get_database_session)
):
    """
    Retrieve paginated list of security events with filtering and sorting.
    
    Args:
        page: Page number (1-based)
        per_page: Number of events per page
        category: Filter by event category
        min_severity: Minimum severity score filter
        max_severity: Maximum severity score filter
        start_date: Start date filter
        end_date: End date filter
        source: Source filter
        sort_by: Field to sort by
        sort_order: Sort order (asc/desc)
        db: Database session
        
    Returns:
        EventListResponse with paginated events
        
    Raises:
        HTTPException: If query fails or invalid parameters
    """
    try:
        # Validate sort parameters
        valid_sort_fields = {"timestamp", "severity", "source", "category"}
        if sort_by not in valid_sort_fields:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid sort field. Must be one of: {', '.join(valid_sort_fields)}"
            )
        
        if sort_order not in {"asc", "desc"}:
            raise HTTPException(
                status_code=400,
                detail="Sort order must be 'asc' or 'desc'"
            )
        
        # Validate severity range
        if min_severity and max_severity and min_severity > max_severity:
            raise HTTPException(
                status_code=400,
                detail="min_severity cannot be greater than max_severity"
            )
        
        # Validate date range
        if start_date and end_date and start_date > end_date:
            raise HTTPException(
                status_code=400,
                detail="start_date cannot be after end_date"
            )
        
        # Build base query
        query = db.query(Event).outerjoin(AIAnalysisModel)
        
        # Apply filters
        filters = []
        
        if category:
            filters.append(Event.category == category)
        
        if source:
            filters.append(Event.source.ilike(f"%{source}%"))
        
        if start_date:
            filters.append(Event.timestamp >= start_date)
        
        if end_date:
            filters.append(Event.timestamp <= end_date)
        
        if min_severity:
            filters.append(AIAnalysisModel.severity_score >= min_severity)
        
        if max_severity:
            filters.append(AIAnalysisModel.severity_score <= max_severity)
        
        if filters:
            query = query.filter(and_(*filters))
        
        # Get total count for pagination
        total = query.count()
        
        # Apply sorting
        if sort_by == "timestamp":
            sort_field = Event.timestamp
        elif sort_by == "severity":
            sort_field = AIAnalysisModel.severity_score
        elif sort_by == "source":
            sort_field = Event.source
        elif sort_by == "category":
            sort_field = Event.category
        
        if sort_order == "desc":
            query = query.order_by(desc(sort_field))
        else:
            query = query.order_by(asc(sort_field))
        
        # Apply pagination
        offset = (page - 1) * per_page
        events = query.offset(offset).limit(per_page).all()
        
        # Convert to response format
        event_responses = []
        for event in events:
            ai_analysis = None
            if event.ai_analysis:
                # Parse recommendations JSON string
                try:
                    import json
                    recommendations = json.loads(event.ai_analysis.recommendations)
                except:
                    recommendations = [event.ai_analysis.recommendations]
                
                ai_analysis = AIAnalysis(
                    id=event.ai_analysis.id,
                    event_id=event.ai_analysis.event_id,
                    severity_score=event.ai_analysis.severity_score,
                    explanation=event.ai_analysis.explanation,
                    recommendations=recommendations,
                    analyzed_at=event.ai_analysis.analyzed_at
                )
            
            event_response = EventResponse(
                id=event.id,
                raw_log_id=event.raw_log_id,
                timestamp=event.timestamp,
                source=event.source,
                message=event.message,
                category=event.category,
                parsed_at=event.parsed_at,
                ai_analysis=ai_analysis
            )
            event_responses.append(event_response)
        
        # Calculate pagination info
        total_pages = (total + per_page - 1) // per_page
        
        return EventListResponse(
            events=event_responses,
            total=total,
            page=page,
            per_page=per_page,
            total_pages=total_pages
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to retrieve events: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to retrieve events: {str(e)}")


@app.get("/event/{event_id}", response_model=EventResponse)
async def get_event_detail(
    event_id: str,
    db: Session = Depends(get_database_session)
):
    """
    Retrieve detailed information for a specific event.
    
    Args:
        event_id: ID of the event to retrieve
        db: Database session
        
    Returns:
        EventResponse with detailed event information and AI analysis
        
    Raises:
        HTTPException: If event not found or query fails
    """
    try:
        # Query event with AI analysis
        event = db.query(Event).outerjoin(AIAnalysisModel).filter(Event.id == event_id).first()
        
        if not event:
            raise HTTPException(
                status_code=404,
                detail=f"Event with ID {event_id} not found"
            )
        
        # Convert AI analysis if available
        ai_analysis = None
        if event.ai_analysis:
            try:
                import json
                recommendations = json.loads(event.ai_analysis.recommendations)
            except:
                recommendations = [event.ai_analysis.recommendations]
            
            ai_analysis = AIAnalysis(
                id=event.ai_analysis.id,
                event_id=event.ai_analysis.event_id,
                severity_score=event.ai_analysis.severity_score,
                explanation=event.ai_analysis.explanation,
                recommendations=recommendations,
                analyzed_at=event.ai_analysis.analyzed_at
            )
        
        return EventResponse(
            id=event.id,
            raw_log_id=event.raw_log_id,
            timestamp=event.timestamp,
            source=event.source,
            message=event.message,
            category=event.category,
            parsed_at=event.parsed_at,
            ai_analysis=ai_analysis
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to retrieve event {event_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to retrieve event: {str(e)}")


@app.get("/stats", response_model=Dict[str, Any])
async def get_system_stats():
    """
    Get system statistics and metrics.
    
    Returns:
        Dictionary with system statistics
    """
    try:
        db_stats = get_database_stats()
        processing_stats = get_processing_stats()
        
        # Add additional stats
        stats = {
            "database": db_stats,
            "processing": processing_stats,
            "api_version": "1.0.0",
            "timestamp": datetime.now(timezone.utc)
        }
        
        return stats
        
    except Exception as e:
        logger.error(f"Failed to get system stats: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to get system stats: {str(e)}")


@app.post("/trigger-processing/{raw_log_id}", response_model=Dict[str, Any])
async def trigger_manual_processing(
    raw_log_id: str,
    background_tasks: BackgroundTasks
):
    """
    Manually trigger processing for a specific raw log.
    
    Args:
        raw_log_id: ID of the raw log to process
        background_tasks: FastAPI background tasks
        
    Returns:
        Processing trigger confirmation
    """
    try:
        # Check if raw log exists
        with get_database_session() as db:
            raw_log = db.query(RawLog).filter(RawLog.id == raw_log_id).first()
            if not raw_log:
                raise HTTPException(
                    status_code=404,
                    detail=f"Raw log with ID {raw_log_id} not found"
                )
        
        # Trigger background processing
        background_tasks.add_task(process_raw_log, raw_log_id)
        
        return {
            "message": f"Processing triggered for raw log {raw_log_id}",
            "raw_log_id": raw_log_id,
            "triggered_at": datetime.now(timezone.utc)
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to trigger processing for {raw_log_id}: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to trigger processing: {str(e)}"
        )


@app.get("/scheduler/status", response_model=Dict[str, Any])
async def get_scheduler_status_endpoint():
    """
    Get current scheduler status and job information.
    
    Returns:
        Dictionary with scheduler status and job details
    """
    try:
        status = get_scheduler_status()
        return status
        
    except Exception as e:
        logger.error(f"Failed to get scheduler status: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to get scheduler status: {str(e)}")


@app.get("/scheduler/audit-log", response_model=List[Dict[str, Any]])
async def get_scheduler_audit_log(
    limit: Optional[int] = Query(50, ge=1, le=1000, description="Maximum number of entries to return")
):
    """
    Get scheduler audit log entries.
    
    Args:
        limit: Maximum number of entries to return
        
    Returns:
        List of audit log entries (most recent first)
    """
    try:
        audit_log = get_audit_log(limit)
        return audit_log
        
    except Exception as e:
        logger.error(f"Failed to get audit log: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to get audit log: {str(e)}")


@app.post("/scheduler/trigger-report", response_model=Dict[str, Any])
async def trigger_manual_report_endpoint(
    report_date: Optional[date] = Query(None, description="Date for the report (defaults to yesterday)")
):
    """
    Manually trigger report generation for a specific date.
    
    Args:
        report_date: Date for which to generate the report
        
    Returns:
        Report generation results
    """
    try:
        result = trigger_manual_report(report_date)
        
        if result["success"]:
            logger.info(f"Manual report generation triggered successfully for {result['report_date']}")
        else:
            logger.error(f"Manual report generation failed: {result.get('error', 'Unknown error')}")
        
        return result
        
    except Exception as e:
        logger.error(f"Failed to trigger manual report: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to trigger manual report: {str(e)}")


@app.get("/reports/files", response_model=List[Dict[str, Any]])
async def get_report_files():
    """
    Get information about existing report files.
    
    Returns:
        List of report file information
    """
    try:
        files_info = get_report_files_info()
        return files_info
        
    except Exception as e:
        logger.error(f"Failed to get report files info: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to get report files info: {str(e)}")


@app.get("/realtime/status", response_model=Dict[str, Any])
async def get_realtime_status():
    """
    Get real-time system status and component information.
    
    Returns:
        Dictionary with real-time system status
    """
    try:
        status = realtime_manager.get_status()
        return status
        
    except Exception as e:
        logger.error(f"Failed to get real-time status: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to get real-time status: {str(e)}")


# WebSocket endpoints

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """
    Main WebSocket endpoint for real-time communication.
    
    Handles client connections and real-time event streaming with authentication.
    """
    try:
        # Get WebSocket API from realtime manager
        websocket_api = realtime_manager.get_websocket_api()
        if not websocket_api:
            await websocket.close(code=1011, reason="WebSocket service unavailable")
            return
        
        # Extract token from query parameters
        query_params = dict(websocket.query_params)
        token = query_params.get("token")
        
        # Handle connection with authentication
        await websocket_api.handle_websocket_connection(websocket, token=token)
        
    except Exception as e:
        logger.error(f"WebSocket endpoint error: {e}")
        try:
            await websocket.close(code=1011, reason="Internal server error")
        except:
            pass


@app.websocket("/ws/{client_id}")
async def websocket_endpoint_with_id(websocket: WebSocket, client_id: str):
    """
    WebSocket endpoint with specific client ID.
    
    Args:
        websocket: WebSocket connection
        client_id: Client identifier
    """
    try:
        # Validate client_id format
        if not client_id or len(client_id) > 100:
            await websocket.close(code=1003, reason="Invalid client ID")
            return
        
        # Get WebSocket API from realtime manager
        websocket_api = realtime_manager.get_websocket_api()
        if not websocket_api:
            await websocket.close(code=1011, reason="WebSocket service unavailable")
            return
        
        # Extract token from query parameters
        query_params = dict(websocket.query_params)
        token = query_params.get("token")
        
        # Handle connection with specific client ID and authentication
        await websocket_api.handle_websocket_connection(websocket, client_id, token)
        
    except Exception as e:
        logger.error(f"WebSocket endpoint error for client {client_id}: {e}")
        try:
            await websocket.close(code=1011, reason="Internal server error")
        except:
            pass


@app.get("/ws/info", response_model=Dict[str, Any])
async def get_websocket_info():
    """
    Get WebSocket server information and statistics.
    
    Returns:
        Dictionary with WebSocket server info
    """
    try:
        websocket_api = realtime_manager.get_websocket_api()
        if not websocket_api:
            raise HTTPException(status_code=503, detail="WebSocket service unavailable")
        
        info = websocket_api.get_connection_info()
        return info
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get WebSocket info: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get WebSocket info: {e}")


@app.get("/report/daily")
async def generate_daily_report_endpoint(
    report_date: Optional[date] = Query(None, description="Date for the report (defaults to today)"),
    db: Session = Depends(get_database_session)
):
    """
    Generate and return a daily PDF security report.
    
    Args:
        report_date: Date for which to generate the report (defaults to today)
        db: Database session
        
    Returns:
        PDF file as response
        
    Raises:
        HTTPException: If report generation fails
    """
    try:
        # Use today's date if not specified
        if report_date is None:
            report_date = date.today()
        
        # Validate date is not in the future
        if report_date > date.today():
            raise HTTPException(
                status_code=400,
                detail="Report date cannot be in the future"
            )
        
        logger.info(f"Generating daily report for {report_date}")
        
        # Generate the report
        file_path, pdf_bytes = generate_daily_report(report_date)
        
        # Save report record to database
        report_id = save_report_record(db, report_date, file_path)
        
        logger.info(f"Daily report generated successfully: {report_id}")
        
        # Return PDF as response
        filename = f"security_report_{report_date.strftime('%Y%m%d')}.pdf"
        
        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={
                "Content-Disposition": f"attachment; filename={filename}",
                "Content-Type": "application/pdf"
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to generate daily report for {report_date}: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to generate report: {str(e)}"
        )


# Demo Mode API Endpoints

@app.get("/metrics", response_model=Dict[str, Any])
async def get_api_metrics():
    """
    Get API performance metrics.
    
    Returns:
        Dictionary with API metrics
    """
    try:
        from app.middleware import get_metrics_middleware
        
        metrics_middleware = get_metrics_middleware()
        if not metrics_middleware:
            raise HTTPException(
                status_code=503,
                detail="Metrics collection not available"
            )
        
        metrics = metrics_middleware.get_metrics()
        
        return {
            "api_metrics": metrics,
            "timestamp": datetime.now(timezone.utc)
        }
        
    except Exception as e:
        logger.error(f"Failed to get API metrics: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to get API metrics: {str(e)}")


@app.get("/demo/status", response_model=Dict[str, Any])
async def get_demo_status(db: Session = Depends(get_database_session)):
    """
    Get demo mode status and available demo data.
    
    Returns:
        Dictionary with demo status and statistics
    """
    try:
        # Check if demo data exists
        raw_logs_count = db.query(RawLog).count()
        events_count = db.query(Event).count()
        analyzed_events_count = db.query(AIAnalysisModel).count()
        
        # Get sample of events for preview
        sample_events = db.query(Event).limit(5).all()
        
        demo_status = {
            "demo_data_available": raw_logs_count > 0,
            "statistics": {
                "raw_logs": raw_logs_count,
                "parsed_events": events_count,
                "analyzed_events": analyzed_events_count,
                "analysis_coverage": (analyzed_events_count / events_count * 100) if events_count > 0 else 0
            },
            "sample_events": [
                {
                    "id": event.id,
                    "timestamp": event.timestamp,
                    "source": event.source,
                    "category": event.category,
                    "message": event.message[:100] + "..." if len(event.message) > 100 else event.message
                }
                for event in sample_events
            ],
            "demo_files_available": [
                "macos_system.log",
                "macos_auth.log"
            ]
        }
        
        return demo_status
        
    except Exception as e:
        logger.error(f"Failed to get demo status: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to get demo status: {str(e)}")


@app.get("/demo/comparison/{event_id}", response_model=Dict[str, Any])
async def get_demo_comparison(
    event_id: str,
    db: Session = Depends(get_database_session)
):
    """
    Get raw vs analyzed comparison for a specific event.
    
    Args:
        event_id: ID of the event to compare
        
    Returns:
        Dictionary with raw log and AI analysis comparison
    """
    try:
        # Get event with raw log and AI analysis
        event = db.query(Event).outerjoin(AIAnalysisModel).filter(Event.id == event_id).first()
        
        if not event:
            raise HTTPException(
                status_code=404,
                detail=f"Event with ID {event_id} not found"
            )
        
        # Get raw log content
        raw_log = db.query(RawLog).filter(RawLog.id == event.raw_log_id).first()
        
        # Find the specific log line that corresponds to this event
        raw_log_line = None
        if raw_log:
            # Try to find the matching line in the raw log
            lines = raw_log.content.split('\n')
            for line in lines:
                if event.message in line or any(word in line for word in event.message.split()[:3]):
                    raw_log_line = line.strip()
                    break
        
        # Prepare AI analysis
        ai_analysis = None
        if event.ai_analysis:
            try:
                import json
                recommendations = json.loads(event.ai_analysis.recommendations)
            except:
                recommendations = [event.ai_analysis.recommendations]
            
            ai_analysis = {
                "severity_score": event.ai_analysis.severity_score,
                "explanation": event.ai_analysis.explanation,
                "recommendations": recommendations,
                "analyzed_at": event.ai_analysis.analyzed_at
            }
        
        comparison = {
            "event_id": event_id,
            "raw_data": {
                "original_log_line": raw_log_line or "Original log line not found",
                "raw_log_source": raw_log.source if raw_log else "Unknown",
                "ingested_at": raw_log.ingested_at if raw_log else None
            },
            "parsed_data": {
                "timestamp": event.timestamp,
                "source": event.source,
                "message": event.message,
                "category": event.category,
                "parsed_at": event.parsed_at
            },
            "ai_analysis": ai_analysis,
            "value_added": {
                "structured_data": "Raw log converted to structured event with timestamp, source, and category",
                "severity_assessment": f"AI assigned severity score of {ai_analysis['severity_score']}/10" if ai_analysis else "No AI analysis available",
                "contextual_explanation": "AI provided human-readable explanation of the security event" if ai_analysis else None,
                "actionable_recommendations": f"{len(ai_analysis['recommendations'])} specific recommendations provided" if ai_analysis else None
            }
        }
        
        return comparison
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get demo comparison for event {event_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to get demo comparison: {str(e)}")


@app.get("/demo/sample-logs", response_model=List[Dict[str, Any]])
async def get_sample_logs():
    """
    Get available sample log files for demo purposes.
    
    Returns:
        List of sample log files with metadata
    """
    try:
        import os
        from pathlib import Path
        
        sample_logs_dir = Path("data/sample_logs")
        sample_files = []
        
        if sample_logs_dir.exists():
            for file_path in sample_logs_dir.glob("*.log"):
                try:
                    with open(file_path, 'r') as f:
                        content = f.read()
                        lines = content.split('\n')
                        non_empty_lines = [line for line in lines if line.strip()]
                    
                    file_info = {
                        "filename": file_path.name,
                        "path": str(file_path),
                        "size_bytes": file_path.stat().st_size,
                        "line_count": len(non_empty_lines),
                        "preview": non_empty_lines[:3] if non_empty_lines else [],
                        "description": _get_log_file_description(file_path.name)
                    }
                    sample_files.append(file_info)
                    
                except Exception as e:
                    logger.warning(f"Could not read sample file {file_path}: {e}")
        
        return sample_files
        
    except Exception as e:
        logger.error(f"Failed to get sample logs: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to get sample logs: {str(e)}")


def _get_log_file_description(filename: str) -> str:
    """Get description for a sample log file."""
    descriptions = {
        "macos_system.log": "macOS system log with kernel messages, sandbox violations, and security events",
        "macos_auth.log": "macOS authentication log with SSH attempts, sudo usage, and authorization events"
    }
    return descriptions.get(filename, "Sample security log file")


@app.post("/demo/load-sample-data", response_model=Dict[str, Any])
async def load_sample_data(
    background_tasks: BackgroundTasks,
    clear_existing: bool = Query(False, description="Clear existing data before loading samples")
):
    """
    Load sample demo data into the system.
    
    Args:
        background_tasks: FastAPI background tasks
        clear_existing: Whether to clear existing data first
        
    Returns:
        Loading status and information
    """
    try:
        # Import the demo data loader
        import subprocess
        import sys
        
        # Prepare command
        cmd = [sys.executable, "demo_data_loader.py", "--quiet"]
        if clear_existing:
            cmd.append("--clear")
        
        # Run the demo data loader
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        
        if result.returncode == 0:
            return {
                "success": True,
                "message": "Demo data loaded successfully",
                "cleared_existing": clear_existing,
                "output": result.stdout,
                "loaded_at": datetime.now(timezone.utc)
            }
        else:
            logger.error(f"Demo data loading failed: {result.stderr}")
            return {
                "success": False,
                "message": "Failed to load demo data",
                "error": result.stderr,
                "output": result.stdout
            }
        
    except subprocess.TimeoutExpired:
        return {
            "success": False,
            "message": "Demo data loading timed out",
            "error": "Loading process exceeded 5 minute timeout"
        }
    except Exception as e:
        logger.error(f"Failed to load sample data: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to load sample data: {str(e)}")


# Real-time Configuration Management API Endpoints

@app.get("/realtime/config", response_model=MonitoringConfigResponse)
async def get_monitoring_config():
    """
    Get current monitoring configuration.
    
    Returns:
        MonitoringConfigResponse with current configuration
    """
    try:
        config_manager = get_config_manager()
        config = config_manager.load_config()
        
        # Convert to response format
        log_sources = []
        for source in config.log_sources:
            log_sources.append(LogSourceConfigResponse(
                source_name=source.source_name,
                path=source.path,
                source_type=source.source_type.value,
                enabled=source.enabled,
                recursive=source.recursive,
                file_pattern=source.file_pattern,
                polling_interval=source.polling_interval,
                batch_size=source.batch_size,
                priority=source.priority,
                description=source.description,
                tags=source.tags,
                status=source.status.value,
                last_monitored=source.last_monitored,
                file_size=source.file_size,
                last_offset=source.last_offset,
                error_message=source.error_message
            ))
        
        notification_rules = []
        for rule in config.notification_rules:
            notification_rules.append(NotificationRuleResponse(
                rule_name=rule.rule_name,
                enabled=rule.enabled,
                min_severity=rule.min_severity,
                max_severity=rule.max_severity,
                categories=rule.categories,
                sources=rule.sources,
                channels=[ch.value for ch in rule.channels],
                throttle_minutes=rule.throttle_minutes,
                email_recipients=rule.email_recipients,
                webhook_url=rule.webhook_url,
                slack_channel=rule.slack_channel
            ))
        
        return MonitoringConfigResponse(
            enabled=config.enabled,
            max_concurrent_sources=config.max_concurrent_sources,
            processing_batch_size=config.processing_batch_size,
            max_queue_size=config.max_queue_size,
            health_check_interval=config.health_check_interval,
            max_error_count=config.max_error_count,
            retry_interval=config.retry_interval,
            file_read_chunk_size=config.file_read_chunk_size,
            websocket_max_connections=config.websocket_max_connections,
            log_sources=log_sources,
            notification_rules=notification_rules,
            config_version=config.config_version,
            created_at=config.created_at,
            updated_at=config.updated_at
        )
        
    except Exception as e:
        logger.error(f"Failed to get monitoring configuration: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get configuration: {e}")


@app.get("/realtime/config/summary", response_model=Dict[str, Any])
async def get_config_summary():
    """
    Get a summary of the current monitoring configuration.
    
    Returns:
        Dictionary with configuration summary
    """
    try:
        config_manager = get_config_manager()
        summary = config_manager.get_configuration_summary()
        return summary
        
    except Exception as e:
        logger.error(f"Failed to get configuration summary: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get configuration summary: {e}")


@app.get("/realtime/log-sources", response_model=List[LogSourceConfigResponse])
async def get_log_sources():
    """
    Get all log source configurations.
    
    Returns:
        List of LogSourceConfigResponse
    """
    try:
        config_manager = get_config_manager()
        sources = config_manager.get_log_sources()
        
        response_sources = []
        for source in sources:
            response_sources.append(LogSourceConfigResponse(
                source_name=source.source_name,
                path=source.path,
                source_type=source.source_type.value,
                enabled=source.enabled,
                recursive=source.recursive,
                file_pattern=source.file_pattern,
                polling_interval=source.polling_interval,
                batch_size=source.batch_size,
                priority=source.priority,
                description=source.description,
                tags=source.tags,
                status=source.status.value,
                last_monitored=source.last_monitored,
                file_size=source.file_size,
                last_offset=source.last_offset,
                error_message=source.error_message
            ))
        
        return response_sources
        
    except Exception as e:
        logger.error(f"Failed to get log sources: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get log sources: {e}")


@app.get("/realtime/log-sources/{source_name}", response_model=LogSourceConfigResponse)
async def get_log_source(source_name: str):
    """
    Get a specific log source configuration.
    
    Args:
        source_name: Name of the log source
        
    Returns:
        LogSourceConfigResponse for the specified source
    """
    try:
        config_manager = get_config_manager()
        source = config_manager.get_log_source(source_name)
        
        if not source:
            raise HTTPException(status_code=404, detail=f"Log source '{source_name}' not found")
        
        return LogSourceConfigResponse(
            source_name=source.source_name,
            path=source.path,
            source_type=source.source_type.value,
            enabled=source.enabled,
            recursive=source.recursive,
            file_pattern=source.file_pattern,
            polling_interval=source.polling_interval,
            batch_size=source.batch_size,
            priority=source.priority,
            description=source.description,
            tags=source.tags,
            status=source.status.value,
            last_monitored=source.last_monitored,
            file_size=source.file_size,
            last_offset=source.last_offset,
            error_message=source.error_message
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get log source {source_name}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get log source: {e}")


@app.post("/realtime/log-sources", response_model=LogSourceConfigResponse)
async def create_log_source(request: LogSourceConfigRequest):
    """
    Create a new log source configuration.
    
    Args:
        request: LogSourceConfigRequest with source configuration
        
    Returns:
        LogSourceConfigResponse for the created source
    """
    try:
        config_manager = get_config_manager()
        
        # Convert request to LogSourceConfig
        source_config = LogSourceConfig(
            source_name=request.source_name,
            path=request.path,
            source_type=LogSourceType(request.source_type),
            enabled=request.enabled,
            recursive=request.recursive,
            file_pattern=request.file_pattern,
            polling_interval=request.polling_interval,
            batch_size=request.batch_size,
            priority=request.priority,
            description=request.description,
            tags=request.tags
        )
        
        # Add the source
        success = config_manager.add_log_source(source_config)
        
        if not success:
            raise HTTPException(status_code=400, detail="Failed to add log source")
        
        # Return the created source
        created_source = config_manager.get_log_source(request.source_name)
        
        return LogSourceConfigResponse(
            source_name=created_source.source_name,
            path=created_source.path,
            source_type=created_source.source_type.value,
            enabled=created_source.enabled,
            recursive=created_source.recursive,
            file_pattern=created_source.file_pattern,
            polling_interval=created_source.polling_interval,
            batch_size=created_source.batch_size,
            priority=created_source.priority,
            description=created_source.description,
            tags=created_source.tags,
            status=created_source.status.value,
            last_monitored=created_source.last_monitored,
            file_size=created_source.file_size,
            last_offset=created_source.last_offset,
            error_message=created_source.error_message
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to create log source: {e}")
        raise HTTPException(status_code=400, detail=f"Failed to create log source: {e}")


@app.put("/realtime/log-sources/{source_name}", response_model=LogSourceConfigResponse)
async def update_log_source(source_name: str, request: LogSourceConfigRequest):
    """
    Update an existing log source configuration.
    
    Args:
        source_name: Name of the log source to update
        request: LogSourceConfigRequest with updated configuration
        
    Returns:
        LogSourceConfigResponse for the updated source
    """
    try:
        config_manager = get_config_manager()
        
        # Convert request to LogSourceConfig
        updated_config = LogSourceConfig(
            source_name=request.source_name,
            path=request.path,
            source_type=LogSourceType(request.source_type),
            enabled=request.enabled,
            recursive=request.recursive,
            file_pattern=request.file_pattern,
            polling_interval=request.polling_interval,
            batch_size=request.batch_size,
            priority=request.priority,
            description=request.description,
            tags=request.tags
        )
        
        # Update the source
        success = config_manager.update_log_source(source_name, updated_config)
        
        if not success:
            raise HTTPException(status_code=404, detail=f"Log source '{source_name}' not found")
        
        # Return the updated source
        updated_source = config_manager.get_log_source(request.source_name)
        
        return LogSourceConfigResponse(
            source_name=updated_source.source_name,
            path=updated_source.path,
            source_type=updated_source.source_type.value,
            enabled=updated_source.enabled,
            recursive=updated_source.recursive,
            file_pattern=updated_source.file_pattern,
            polling_interval=updated_source.polling_interval,
            batch_size=updated_source.batch_size,
            priority=updated_source.priority,
            description=updated_source.description,
            tags=updated_source.tags,
            status=updated_source.status.value,
            last_monitored=updated_source.last_monitored,
            file_size=updated_source.file_size,
            last_offset=updated_source.last_offset,
            error_message=updated_source.error_message
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update log source {source_name}: {e}")
        raise HTTPException(status_code=400, detail=f"Failed to update log source: {e}")


@app.delete("/realtime/log-sources/{source_name}", response_model=Dict[str, str])
async def delete_log_source(source_name: str):
    """
    Delete a log source configuration.
    
    Args:
        source_name: Name of the log source to delete
        
    Returns:
        Confirmation message
    """
    try:
        config_manager = get_config_manager()
        
        success = config_manager.remove_log_source(source_name)
        
        if not success:
            raise HTTPException(status_code=404, detail=f"Log source '{source_name}' not found")
        
        return {"message": f"Log source '{source_name}' deleted successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete log source {source_name}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to delete log source: {e}")


@app.post("/realtime/log-sources/{source_name}/test", response_model=Dict[str, Any])
async def test_log_source(source_name: str):
    """
    Test a log source configuration for connectivity and permissions.
    
    Args:
        source_name: Name of the log source to test
        
    Returns:
        Test results with status and details
    """
    try:
        config_manager = get_config_manager()
        
        # Get the log source configuration
        log_sources = config_manager.get_log_sources()
        source_config = None
        for source in log_sources:
            if source.source_name == source_name:
                source_config = source
                break
        
        if not source_config:
            raise HTTPException(status_code=404, detail=f"Log source '{source_name}' not found")
        
        # Test the log source
        import os
        import stat
        from pathlib import Path
        
        test_results = {
            "status": "success",
            "message": "Log source test completed",
            "details": {
                "path": source_config.path,
                "source_type": source_config.source_type,
                "file_exists": False,
                "readable": False,
                "file_size": 0,
                "last_modified": None,
                "permissions": None,
                "error_message": None
            }
        }
        
        try:
            path = Path(source_config.path)
            
            # Check if path exists
            if path.exists():
                test_results["details"]["file_exists"] = True
                
                # Check if readable
                if os.access(str(path), os.R_OK):
                    test_results["details"]["readable"] = True
                    
                    # Get file/directory stats
                    stat_info = path.stat()
                    test_results["details"]["file_size"] = stat_info.st_size
                    test_results["details"]["last_modified"] = stat_info.st_mtime
                    test_results["details"]["permissions"] = oct(stat_info.st_mode)[-3:]
                    
                    # For directories, check if we can list contents
                    if source_config.source_type == "directory" and path.is_dir():
                        try:
                            files = list(path.iterdir())
                            test_results["details"]["directory_files"] = len(files)
                            
                            # If file pattern is specified, check for matching files
                            if source_config.file_pattern:
                                import fnmatch
                                matching_files = [f for f in files if f.is_file() and fnmatch.fnmatch(f.name, source_config.file_pattern)]
                                test_results["details"]["matching_files"] = len(matching_files)
                        except PermissionError:
                            test_results["details"]["error_message"] = "Permission denied when listing directory contents"
                            test_results["status"] = "warning"
                    
                    # For files, try to read a small sample
                    elif source_config.source_type == "file" and path.is_file():
                        try:
                            with open(path, 'r', encoding='utf-8', errors='ignore') as f:
                                sample = f.read(1024)  # Read first 1KB
                                test_results["details"]["sample_content_length"] = len(sample)
                                test_results["details"]["has_content"] = len(sample.strip()) > 0
                        except Exception as e:
                            test_results["details"]["error_message"] = f"Error reading file: {str(e)}"
                            test_results["status"] = "warning"
                else:
                    test_results["details"]["error_message"] = "File/directory is not readable"
                    test_results["status"] = "error"
            else:
                test_results["details"]["error_message"] = "File/directory does not exist"
                test_results["status"] = "error"
                
        except Exception as e:
            test_results["details"]["error_message"] = f"Test failed: {str(e)}"
            test_results["status"] = "error"
        
        return test_results
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to test log source {source_name}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to test log source: {e}")


@app.get("/realtime/config/validate", response_model=Dict[str, Any])
async def validate_config():
    """
    Validate the current monitoring configuration.
    
    Returns:
        Dictionary with validation results
    """
    try:
        config_manager = get_config_manager()
        issues = config_manager.validate_configuration()
        
        return {
            "valid": len(issues) == 0,
            "issues": issues,
            "issue_count": len(issues),
            "validated_at": datetime.now(timezone.utc)
        }
        
    except Exception as e:
        logger.error(f"Failed to validate configuration: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to validate configuration: {e}")


# Notification Rule Management Endpoints

@app.get("/realtime/notification-rules", response_model=List[NotificationRuleResponse])
async def get_notification_rules():
    """
    Get all notification rules.
    
    Returns:
        List of notification rule configurations
    """
    try:
        config_manager = get_config_manager()
        config = config_manager.load_config()
        
        return config.notification_rules
        
    except Exception as e:
        logger.error(f"Failed to get notification rules: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get notification rules: {e}")


@app.get("/realtime/notification-rules/{rule_name}", response_model=NotificationRuleResponse)
async def get_notification_rule(rule_name: str):
    """
    Get a specific notification rule by name.
    
    Args:
        rule_name: Name of the notification rule
        
    Returns:
        Notification rule configuration
    """
    try:
        config_manager = get_config_manager()
        config = config_manager.load_config()
        
        for rule in config.notification_rules:
            if rule.rule_name == rule_name:
                return rule
        
        raise HTTPException(status_code=404, detail=f"Notification rule '{rule_name}' not found")
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get notification rule {rule_name}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get notification rule: {e}")


@app.post("/realtime/notification-rules", response_model=NotificationRuleResponse)
async def create_notification_rule(request: NotificationRuleRequest):
    """
    Create a new notification rule.
    
    Args:
        request: Notification rule configuration
        
    Returns:
        Created notification rule
    """
    try:
        config_manager = get_config_manager()
        config = config_manager.load_config()
        
        # Check if rule name already exists
        for existing_rule in config.notification_rules:
            if existing_rule.rule_name == request.rule_name:
                raise HTTPException(status_code=400, detail=f"Notification rule '{request.rule_name}' already exists")
        
        # Create new notification rule
        from app.realtime.models import NotificationRule
        new_rule = NotificationRule(
            rule_name=request.rule_name,
            enabled=request.enabled,
            min_severity=request.min_severity,
            max_severity=request.max_severity,
            categories=request.categories,
            sources=request.sources,
            channels=request.channels,
            throttle_minutes=request.throttle_minutes,
            email_recipients=request.email_recipients,
            webhook_url=request.webhook_url,
            slack_channel=request.slack_channel
        )
        
        # Add to configuration
        config.notification_rules.append(new_rule)
        
        # Save configuration
        success = config_manager.save_config(config)
        if not success:
            raise HTTPException(status_code=500, detail="Failed to save notification rule configuration")
        
        logger.info(f"Created notification rule: {request.rule_name}")
        return new_rule
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to create notification rule: {e}")
        raise HTTPException(status_code=400, detail=f"Failed to create notification rule: {e}")


@app.put("/realtime/notification-rules/{rule_name}", response_model=NotificationRuleResponse)
async def update_notification_rule(rule_name: str, request: NotificationRuleRequest):
    """
    Update an existing notification rule.
    
    Args:
        rule_name: Name of the notification rule to update
        request: Updated notification rule configuration
        
    Returns:
        Updated notification rule
    """
    try:
        config_manager = get_config_manager()
        config = config_manager.load_config()
        
        # Find the rule to update
        rule_index = None
        for i, rule in enumerate(config.notification_rules):
            if rule.rule_name == rule_name:
                rule_index = i
                break
        
        if rule_index is None:
            raise HTTPException(status_code=404, detail=f"Notification rule '{rule_name}' not found")
        
        # If rule name is changing, check for conflicts
        if request.rule_name != rule_name:
            for existing_rule in config.notification_rules:
                if existing_rule.rule_name == request.rule_name:
                    raise HTTPException(status_code=400, detail=f"Notification rule '{request.rule_name}' already exists")
        
        # Update the rule
        from app.realtime.models import NotificationRule
        updated_rule = NotificationRule(
            rule_name=request.rule_name,
            enabled=request.enabled,
            min_severity=request.min_severity,
            max_severity=request.max_severity,
            categories=request.categories,
            sources=request.sources,
            channels=request.channels,
            throttle_minutes=request.throttle_minutes,
            email_recipients=request.email_recipients,
            webhook_url=request.webhook_url,
            slack_channel=request.slack_channel
        )
        
        config.notification_rules[rule_index] = updated_rule
        
        # Save configuration
        success = config_manager.save_config(config)
        if not success:
            raise HTTPException(status_code=500, detail="Failed to save notification rule configuration")
        
        logger.info(f"Updated notification rule: {rule_name} -> {request.rule_name}")
        return updated_rule
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update notification rule {rule_name}: {e}")
        raise HTTPException(status_code=400, detail=f"Failed to update notification rule: {e}")


@app.delete("/realtime/notification-rules/{rule_name}", response_model=Dict[str, str])
async def delete_notification_rule(rule_name: str):
    """
    Delete a notification rule.
    
    Args:
        rule_name: Name of the notification rule to delete
        
    Returns:
        Confirmation message
    """
    try:
        config_manager = get_config_manager()
        config = config_manager.load_config()
        
        # Find and remove the rule
        original_count = len(config.notification_rules)
        config.notification_rules = [rule for rule in config.notification_rules if rule.rule_name != rule_name]
        
        if len(config.notification_rules) == original_count:
            raise HTTPException(status_code=404, detail=f"Notification rule '{rule_name}' not found")
        
        # Save configuration
        success = config_manager.save_config(config)
        if not success:
            raise HTTPException(status_code=500, detail="Failed to save notification rule configuration")
        
        logger.info(f"Deleted notification rule: {rule_name}")
        return {"message": f"Notification rule '{rule_name}' deleted successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete notification rule {rule_name}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to delete notification rule: {e}")


@app.post("/realtime/notification-rules/{rule_name}/test", response_model=Dict[str, str])
async def test_notification_rule(rule_name: str, test_data: Dict[str, Any]):
    """
    Test a notification rule by sending a test notification.
    
    Args:
        rule_name: Name of the notification rule to test
        test_data: Test event data (severity, category, source, message)
        
    Returns:
        Test result message
    """
    try:
        config_manager = get_config_manager()
        config = config_manager.load_config()
        
        # Find the rule
        rule = None
        for r in config.notification_rules:
            if r.rule_name == rule_name:
                rule = r
                break
        
        if not rule:
            raise HTTPException(status_code=404, detail=f"Notification rule '{rule_name}' not found")
        
        if not rule.enabled:
            raise HTTPException(status_code=400, detail=f"Notification rule '{rule_name}' is disabled")
        
        # Create test event data
        test_severity = test_data.get('severity', 8)
        test_category = test_data.get('category', 'security')
        test_source = test_data.get('source', 'test')
        test_message = test_data.get('message', 'This is a test notification')
        
        # Check if rule matches test data
        if test_severity < rule.min_severity or test_severity > rule.max_severity:
            return {"message": f"Test notification not sent - severity {test_severity} is outside rule range ({rule.min_severity}-{rule.max_severity})"}
        
        if rule.categories and test_category not in rule.categories:
            return {"message": f"Test notification not sent - category '{test_category}' not in rule categories"}
        
        if rule.sources and test_source not in rule.sources:
            return {"message": f"Test notification not sent - source '{test_source}' not in rule sources"}
        
        # Send test notification through each channel
        from app.realtime.notifications import NotificationManager
        notification_manager = NotificationManager()
        
        # Create mock event for testing
        mock_event = {
            'id': 'test-event-' + str(int(time.time())),
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'source': test_source,
            'category': test_category,
            'message': test_message,
            'severity': test_severity
        }
        
        try:
            await notification_manager.send_test_notification(rule, mock_event)
            return {"message": f"Test notification sent successfully via {', '.join(rule.channels)}"}
        except Exception as e:
            logger.error(f"Failed to send test notification: {e}")
            return {"message": f"Test notification failed: {str(e)}"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to test notification rule {rule_name}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to test notification rule: {e}")


@app.get("/realtime/notification-history", response_model=List[Dict[str, Any]])
async def get_notification_history(limit: int = 50):
    """
    Get notification history.
    
    Args:
        limit: Maximum number of history records to return
        
    Returns:
        List of notification history records
    """
    try:
        # Get notification history from database
        with get_db_session() as db:
            from app.models import NotificationHistory
            
            history_records = db.query(NotificationHistory)\
                .order_by(NotificationHistory.sent_at.desc())\
                .limit(limit)\
                .all()
            
            history_data = []
            for record in history_records:
                history_data.append({
                    'id': record.id,
                    'rule_name': record.notification_type,  # Using notification_type as rule_name
                    'event_id': record.event_id,
                    'channel': record.channel,
                    'status': record.status,
                    'sent_at': record.sent_at.isoformat(),
                    'error_message': record.error_message,
                    'event_summary': f"Event {record.event_id}"  # Basic summary
                })
            
            return history_data
        
    except Exception as e:
        logger.error(f"Failed to get notification history: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get notification history: {e}")


if __name__ == "__main__":
    import uvicorn
    
    # Get configuration from environment
    host = os.getenv("HOST", "127.0.0.1")
    port = int(os.getenv("PORT", "8000"))
    debug = os.getenv("DEBUG", "false").lower() == "true"
    
    uvicorn.run(
        "main:app",
        host=host,
        port=port,
        reload=debug,
        log_level="info"
    )