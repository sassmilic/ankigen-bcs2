"""Command-line interface for the Anki vocabulary generator."""

import asyncio
import click
import structlog
from pathlib import Path

from .config import INPUT_WORDS_FILE, MODEL_NAME, BATCH_SIZE, MAX_PARALLEL_REQUESTS, TEMPERATURE
from .pipeline import process
from .utils import (
    load_words_from_file, init_database, write_anki_csv, generate_copy_script
)

# Configure logging
structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
        structlog.processors.JSONRenderer()
    ],
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    wrapper_class=structlog.stdlib.BoundLogger,
    cache_logger_on_first_use=True,
)

log = structlog.get_logger()


@click.command()
@click.option(
    "-i", "--input",
    type=click.Path(exists=True, path_type=Path),
    default=INPUT_WORDS_FILE,
    help="Input file with words (one per line)"
)
@click.option(
    "--model",
    default=MODEL_NAME,
    help="OpenAI model to use"
)
@click.option(
    "--batch-size",
    type=int,
    default=BATCH_SIZE,
    help="Batch size for processing"
)
@click.option(
    "--max-parallel",
    type=int,
    default=MAX_PARALLEL_REQUESTS,
    help="Maximum parallel API requests"
)
@click.option(
    "--temperature",
    type=float,
    default=TEMPERATURE,
    help="Image generation temperature (0.0-1.0, lower = more consistent)"
)
@click.option(
    "--force",
    is_flag=True,
    help="Force reprocessing of already processed words"
)
@click.option(
    "--dry-run",
    is_flag=True,
    help="Show what would be processed without actually doing it"
)
@click.option(
    "--verbose", "-v",
    is_flag=True,
    help="Enable verbose logging"
)
def main(input: Path, model: str, batch_size: int, max_parallel: int, 
         temperature: float, force: bool, dry_run: bool, verbose: bool):
    """Generate Anki cards from BCS vocabulary words."""
    
    # Configure logging level
    if verbose:
        import logging
        logging.basicConfig(level=logging.INFO)
        structlog.configure(
            processors=[
                structlog.stdlib.filter_by_level,
                structlog.stdlib.add_logger_name,
                structlog.stdlib.add_log_level,
                structlog.stdlib.PositionalArgumentsFormatter(),
                structlog.processors.TimeStamper(fmt="iso"),
                structlog.processors.StackInfoRenderer(),
                structlog.processors.format_exc_info,
                structlog.processors.UnicodeDecoder(),
                structlog.dev.ConsoleRenderer()
            ],
            context_class=dict,
            logger_factory=structlog.stdlib.LoggerFactory(),
            wrapper_class=structlog.stdlib.BoundLogger,
            cache_logger_on_first_use=True,
        )
    
    log.info("Starting Anki vocabulary generator", 
             input_file=str(input),
             model=model,
             batch_size=batch_size,
             max_parallel=max_parallel,
             temperature=temperature,
             force=force,
             dry_run=dry_run)
    
    try:
        # Initialize database
        init_database()
        
        # Load words
        words = load_words_from_file(input)
        if not words:
            log.warning("No words found in input file")
            return
        
        log.info("Loaded words", count=len(words))
        
        if dry_run:
            log.info("Dry run mode - would process words", words=words[:10])  # Show first 10
            return
        
        # Process words
        async def run_pipeline():
            return await process(words, force=force, temperature=temperature)
        
        results = asyncio.run(run_pipeline())
        
        # Filter successful results
        successful_words = [r.word for r in results if r.word.canonical_form]
        
        if successful_words:
            # Generate output files
            write_anki_csv(successful_words)
            generate_copy_script()
            
            log.info("Processing completed successfully", 
                     total_words=len(words),
                     successful=len(successful_words),
                     failed=len(words) - len(successful_words))
        else:
            log.error("No words were processed successfully")
            
    except Exception as e:
        log.error("Processing failed", error=str(e))
        raise click.ClickException(str(e))


if __name__ == "__main__":
    main() 