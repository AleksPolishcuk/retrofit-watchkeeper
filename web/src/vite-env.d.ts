/// <reference types="vite/client" />

interface ImportMetaEnv {
  /** "1" when the interface is built to read the saved answers in /snapshot instead of a server */
  readonly VITE_SNAPSHOT?: string
}
