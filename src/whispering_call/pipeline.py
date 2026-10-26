"""Orquestra o fluxo: listar gravações → transcrever → abrir o Claude.

Primeiro transcreve todas as gravações novas (a etapa longa e sem interação) e
só depois abre o Claude para cada doc pendente, para que o usuário não precise
esperar entre uma sessão interativa e outra.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol

from whispering_call.claude_launcher import ClaudeLauncher, ClaudeSession
from whispering_call.claude_prompt import build_initial_prompt
from whispering_call.errors import ClaudeLaunchError, PromptFileError
from whispering_call.meeting_workspace import MeetingWorkspace, workspace_for
from whispering_call.recordings import Recording, RecordingSource
from whispering_call.transcript_markdown import render_transcript_markdown
from whispering_call.transcription import Transcriber

logger = logging.getLogger(__name__)


class RunReporter(Protocol):
    """Saída para o usuário (texto simples), separada dos logs JSON."""

    def info(self, message: str) -> None: ...

    def progress(self, recording_key: str, fraction: float) -> None: ...


@dataclass
class RunSummary:
    transcribed: list[str] = field(default_factory=list)
    launched: list[str] = field(default_factory=list)
    already_documented: list[str] = field(default_factory=list)
    failed: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class _MeetingJob:
    recording: Recording
    workspace: MeetingWorkspace


class MeetingDocPipeline:
    """Processa todas as gravações que ainda não têm ``doc.md``.

    Exemplo::

        pipeline = MeetingDocPipeline(source, transcriber, launcher,
                                      Path("output"), Path("prompts/doc_prompt.md"), reporter)
        summary = pipeline.run()
    """

    def __init__(
        self,
        source: RecordingSource,
        transcriber: Transcriber,
        launcher: ClaudeLauncher,
        output_root: Path,
        prompt_file: Path,
        reporter: RunReporter,
    ) -> None:
        self._source = source
        self._transcriber = transcriber
        self._launcher = launcher
        self._output_root = output_root
        self._prompt_file = prompt_file
        self._reporter = reporter

    def run(self) -> RunSummary:
        prompt_text = read_prompt_template(self._prompt_file)
        summary = RunSummary()
        pending_jobs = self._collect_pending_jobs(summary)
        transcribed_jobs = [
            job for job in pending_jobs if self._ensure_transcript(job, summary)
        ]
        for job in transcribed_jobs:
            self._launch_claude(job, prompt_text, summary)
        return summary

    def _collect_pending_jobs(self, summary: RunSummary) -> list[_MeetingJob]:
        jobs = [
            _MeetingJob(recording, workspace_for(recording, self._output_root))
            for recording in self._source.list_recordings()
        ]
        summary.already_documented.extend(
            j.recording.key for j in jobs if j.workspace.has_doc()
        )
        return [job for job in jobs if not job.workspace.has_doc()]

    def _ensure_transcript(self, job: _MeetingJob, summary: RunSummary) -> bool:
        if job.workspace.has_transcript():
            return True
        key = job.recording.key
        self._reporter.info(f"Transcrevendo {key}...")
        try:
            segments = self._transcriber.transcribe(
                job.recording.media_file,
                lambda fraction: self._reporter.progress(key, fraction),
            )
        # Amplo de propósito: uma gravação corrompida (erro do PyAV/CTranslate2)
        # não deve impedir as demais; o traceback vai para o log JSON.
        except Exception as error:
            return self._record_failure(job, "transcription", error, summary)
        job.workspace.save_transcript(render_transcript_markdown(key, segments))
        summary.transcribed.append(key)
        return True

    def _launch_claude(
        self, job: _MeetingJob, prompt_text: str, summary: RunSummary
    ) -> None:
        workspace = job.workspace
        prompt_copy = workspace.save_prompt_copy(prompt_text)
        initial_prompt = build_initial_prompt(
            prompt_copy, workspace.transcript_file, workspace.doc_file
        )
        self._reporter.info(f"Abrindo Claude Code para {job.recording.key}...")
        try:
            self._launcher.launch(ClaudeSession(workspace.folder, initial_prompt))
        except ClaudeLaunchError as error:
            self._record_failure(job, "claude", error, summary)
            return
        summary.launched.append(job.recording.key)

    def _record_failure(
        self, job: _MeetingJob, stage: str, error: Exception, summary: RunSummary
    ) -> bool:
        fields = {"recording": job.recording.key, "stage": stage, "error": str(error)}
        logger.exception("pipeline_stage_failed", extra={"fields": fields})
        self._reporter.info(f"Falha na etapa {stage} de {job.recording.key}: {error}")
        summary.failed.append(job.recording.key)
        return False


def read_prompt_template(prompt_file: Path) -> str:
    """Lê o prompt de geração da doc; falha cedo se ausente ou vazio.

    Exemplo::

        read_prompt_template(Path("prompts/doc_prompt.md"))
    """
    if not prompt_file.is_file():
        raise PromptFileError(
            f"Prompt de geração da doc não encontrado: {prompt_file} "
            "(esperado um arquivo .md; ajuste [claude].prompt_file)"
        )
    prompt_text = prompt_file.read_text(encoding="utf-8")
    if not prompt_text.strip():
        raise PromptFileError(f"Prompt de geração da doc está vazio: {prompt_file}")
    return prompt_text
