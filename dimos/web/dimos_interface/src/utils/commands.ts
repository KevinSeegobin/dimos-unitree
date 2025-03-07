import packageJson from '../../package.json';
import themes from '../../themes.json';
import { get } from 'svelte/store';
import { history } from '../stores/history';
import { theme } from '../stores/theme';
import { fetchAvailableStreams, startStream, stopStream } from '../stores/stream';
import { simulationStore, type SimulationState } from '../utils/simulation';

let bloop: string | null = null;
const hostname = window.location.hostname;
const bleepbloop = import.meta.env.VITE_ENV_VARIABLE;
const xXx_VaRiAbLeOfDeAtH_xXx = "01011010 01000100 01000110 01110100 01001101 00110010 00110100 01101011 01100001 01010111 00111001 01110101 01011000 01101010 01000101 01100111 01011001 01111010 01000010 01110100 01010000 00110011 01010110 01010101 01001101 01010111 00110101 01101110";
function someRandomFunctionIforget(binary: string): string {
  return atob(binary.split(' ').map(bin => String.fromCharCode(parseInt(bin, 2))).join(''));
}
const var23temp_pls_dont_touch = someRandomFunctionIforget(xXx_VaRiAbLeOfDeAtH_xXx);
const magic_url = "https://agsu5pgehztgo2fuuyip6dwuna0uneua.lambda-url.us-east-2.on.aws/";

export const commands: Record<string, (args: string[]) => Promise<string> | string> = {
  help: () => 'Available commands: ' + Object.keys(commands).join(', '),
  hostname: () => hostname,
  whoami: () => 'guest',
  build: () => 'Actively hiring all-stars. Build the future of dimensional computing with us. Reach out to build@dimensionalOS.com',
  date: () => new Date().toLocaleString(),
  vi: () => `why use vi? try 'vim'`,
  emacs: () => `why use emacs? try 'vim'`,
  echo: (args: string[]) => args.join(' '),
  sudo: (args: string[]) => {
    window.open('https://www.youtube.com/watch?v=dQw4w9WgXcQ');

    return `Permission denied: unable to run the command '${args[0]}'. Not based.`;
  },
  clear: () => {
    history.set([]);

    return '';
  },
  contact: () => {
    window.open(`mailto:${packageJson.author.email}`);

    return `Opening mailto:${packageJson.author.email}...`;
  },
  donate: () => {
    window.open(packageJson.donate.url, '_blank');

    return 'Opening donation url...';
  },
    invest: () => {
    window.open(packageJson.funding.url, '_blank');

    return 'Opening SAFE url...';
  },
  weather: async (args: string[]) => {
    const city = args.join('+');

    if (!city) {
      return 'Usage: weather [city]. Example: weather Brussels';
    }

    const weather = await fetch(`https://wttr.in/${city}?ATm`);

    return weather.text();
  },

  ls: () => {
    return 'whitepaper.txt';
  },
    cd: () => {
    return 'Permission denied: you are not that guy, pal';
  },
  curl: async (args: string[]) => {
    if (args.length === 0) {
      return 'curl: no URL provided';
    }

    const url = args[0];

    try {
      const response = await fetch(url);
      const data = await response.text();

      return data;
    } catch (error) {
      return `curl: could not fetch URL ${url}. Details: ${error}`;
    }
  },
  banner: () => `

██████╗ ██╗███╗   ███╗███████╗███╗   ██╗███████╗██╗ ██████╗ ███╗   ██╗ █████╗ ██╗     
██╔══██╗██║████╗ ████║██╔════╝████╗  ██║██╔════╝██║██╔═══██╗████╗  ██║██╔══██╗██║     
██║  ██║██║██╔████╔██║█████╗  ██╔██╗ ██║███████╗██║██║   ██║██╔██╗ ██║███████║██║     
██║  ██║██║██║╚██╔╝██║██╔══╝  ██║╚██╗██║╚════██║██║██║   ██║██║╚██╗██║██╔══██║██║     
██████╔╝██║██║ ╚═╝ ██║███████╗██║ ╚████║███████║██║╚██████╔╝██║ ╚████║██║  ██║███████╗
╚═════╝ ╚═╝╚═╝     ╚═╝╚══════╝╚═╝  ╚═══╝╚══════╝╚═╝ ╚═════╝ ╚═╝  ╚═══╝╚═╝  ╚═╝╚══════╝v${packageJson.version}

Powering generalist robotics 

Type 'help' to see list of available commands.
`,
  vim: async (args: string[])=> {
    const filename = args.join(' ');

    if (!filename) {
      return 'Usage: vim [filename]. Example: vim robbie.txt';
    }

    if (filename === "whitepaper.txt") {
      if (bloop === null) {
        return `File ${filename} is encrypted. Use 'vim -x ${filename}' to access.`;
      } else {
        return `Incorrect encryption key for ${filename}. Access denied.`;
      }
    }

      if (args[0] === '-x' && args[1] === "whitepaper.txt") {

        const bloop_master = prompt("Enter encryption key:");

        if (bloop_master === var23temp_pls_dont_touch) {
          try {
            const response = await fetch(magic_url, {
              method: 'POST',
              headers: {
                'Content-Type': 'application/json',
              },
              body: JSON.stringify({key: bloop_master}),
            });

            if (response.status === 403) {
              return "Access denied. You are not worthy.";
            }

            if (response.ok) {
              const manifestoText = await response.text();
              bloop = bloop_master;
              return manifestoText;
            } else {
              return "Failed to retrieve. You are not worthy.";
            }
          } catch (error) {
            return `Error: ${error.message}`;
          }
        } else {
          return "Access denied. You are not worthy.";
        }

      }

    return `bash: ${filename}: No such file`;
  },
  simulate: (args: string[]) => {
    if (args.length === 0) {
      return 'Usage: simulate [start|stop] - Start or stop the simulation stream';
    }

    const command = args[0].toLowerCase();

    if (command === 'stop') {
      stopStream();
      return 'Stream stopped.';
    }

    if (command === 'start') {
      // Fetch the streams and start the first one
      fetchAvailableStreams()
        .then(streams => {
          if (streams.length > 0) {
            startStream(streams[0]);
          }
        })
        .catch(err => console.error('Error fetching streams:', err));
      
      return 'Starting simulation stream... Use "simulate stop" to end the stream';
    }

    return 'Invalid command. Use "simulate start" to begin or "simulate stop" to end.';
  },
  control: async (args: string[]) => {
    if (args.length === 0) {
      return 'Usage: control [joint_positions] - Send comma-separated joint positions to control the robot\nExample: control 0,0,0.5,1,0.3';
    }

    const state = get(simulationStore) as SimulationState;
    if (!state.connection) {
      return 'Error: No active simulation. Use "simulate start" first.';
    }

    const jointPositions = args.join(' ');
    
    try {
      const jointPositionsArray = jointPositions.split(',').map(x => parseFloat(x.trim()));
      const response = await fetch(`${state.connection.url}/control?t=${Date.now()}`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Accept': 'application/json'
        },
        body: JSON.stringify({ joint_positions: jointPositionsArray })
      });

      const data = await response.json();
      
      if (response.ok) {
        return `${data.message} ✓`;
      } else {
        return `Error: ${data.message}`;
      }
    } catch (error: unknown) {
      const errorMessage = error instanceof Error ? error.message : 'Unknown error';
      return `Failed to send command: ${errorMessage}. Make sure the simulator is running.`;
    }
  },
  unitree: async (args: string[]) => {
    const [subcommand, ...rest] = args;

    if (!subcommand) {
      return 'Usage: unitree [command] [args]';
    }

    switch (subcommand) {
      case 'status':
        try {
          const response = await fetch('http://localhost:5555/unitree/status');
          const data = await response.json();
          return `Unitree API status: ${data.status}`;
        } catch (error: unknown) {
          const errorMessage = error instanceof Error ? error.message : String(error);
          return `Failed to connect to Unitree API: ${errorMessage}`;
        }

      case 'command':
        try {
          const commandText = rest.join(' ');
          if (!commandText) {
            return 'Usage: unitree command <text>';
          }
          
          const response = await fetch('http://localhost:5555/unitree/command', {
            method: 'POST',
            headers: {
              'Content-Type': 'application/json'
            },
            body: JSON.stringify({ command: commandText })
          });
          
          const data = await response.json();
          return data.success 
            ? `Command sent: ${commandText}`
            : `Error: ${data.message}`;
        } catch (error: unknown) {
          const errorMessage = error instanceof Error ? error.message : String(error);
          return `Failed to send command: ${errorMessage}`;
        }

      case 'start_stream':
        try {
          const streams = await fetchAvailableStreams();
          if (streams.length === 0) {
            return 'No video streams available';
          }
          
          // Default to the first stream if none specified
          const streamKey = rest[0] || streams[0];
          startStream(streamKey);
          return `Started video stream: ${streamKey}`;
        } catch (error: unknown) {
          const errorMessage = error instanceof Error ? error.message : String(error);
          return `Failed to start stream: ${errorMessage}`;
        }

      case 'stop_stream':
        stopStream();
        return 'Video stream stopped';

      default:
        return `Unknown unitree command: ${subcommand}`;
    }
  },
};
