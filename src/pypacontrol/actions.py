"""Explicitly enabled Online Command actions. Validate physical motion externally."""
import math
from .api import check_index, UnsupportedFeatureError

class ActionsDisabledError(PermissionError):
    """Physical actions need explicit enable_actions=True."""

class OnlineActions:
    def _require_actions(self):
        if not self.enable_actions:
            raise ActionsDisabledError('Commands changing machine state are disabled. Set enable_actions=True after safety validation.')

    def _action(self, code, parameter=0, *, value=0, numeric_type=0):
        self._require_actions()
        return self.command(code, parameter=parameter, data_type=numeric_type, value=value)

    def start_online(self):
        return self._action('0603')

    def abort_online(self):
        return self._action('0A81')

    def start_auto(self):
        return self._action('0602')

    def abort_auto(self):
        return self._action('0A41')

    def stop(self):
        """Software stop (0600); never a substitute for emergency stop."""
        return self._action('0600')

    def _motion(self, axis, value, code):
        check_index('axis', axis, 16)
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
            raise ValueError('Position must be a finite number')
        return self._action(code, axis, value=float(value), numeric_type=1)

    def move_absolute(self, axis: int, position: float, *, asynchronous=False):
        """0A87 awaits completion by polling; 0A94 accepts command without waiting."""
        return self._motion(axis, position, '0A94' if asynchronous else '0A87')

    def move_relative(self, axis: int, distance: float, *, asynchronous=False):
        return self._motion(axis, distance, '0A95' if asynchronous else '0A89')

    def stop_axis(self, axis: int):
        check_index('axis', axis, 16)
        return self._action('0A9A', axis)

    def abort_axis_move(self, axis: int):
        check_index('axis', axis, 16)
        return self._action('0A93', axis)

    def reference_axis(self, axis: int):
        check_index('axis', axis, 16)
        return self._action('0A84', axis)

    def set_speed(self, axis: int, speed: float):
        check_index('axis', axis, 16)
        if isinstance(speed, bool) or not isinstance(speed, (int,float)) or not math.isfinite(speed) or speed <= 0:
            raise ValueError('speed must be a finite positive number')
        return self._action('0A8D', axis, value=float(speed), numeric_type=1)

    def set_acceleration(self, axis: int, acceleration: float):
        check_index('axis', axis, 16)
        if isinstance(acceleration, bool) or not isinstance(acceleration, (int,float)) or not math.isfinite(acceleration) or acceleration <= 0:
            raise ValueError('acceleration must be a finite positive number')
        return self._action('0A8E', axis, value=float(acceleration), numeric_type=1)

    def set_output(self, index: int, value: bool):
        """Set digital output O[index] using Online Command 0902."""
        check_index('output', index, 1024)
        if not isinstance(value, bool):
            raise ValueError('value must be a bool')
        return self._action('0902', index, value=int(value))

    def set_register(self, index: int, value, *, kind='int'):
        """Write N-register (0906) or R-register (0907), via Online Command."""
        check_index('register', index, 1024)
        if kind == 'int':
            if isinstance(value, bool) or not isinstance(value, int) or not -(2**31-1) <= value <= 2**31-1:
                raise ValueError('integer register value must be a signed 32-bit integer in documented range')
            return self._action('0906', index, value=value)
        if kind == 'float':
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
                raise ValueError('float register value must be finite')
            # 32-bit IEEE value range, encoded as decimal ASCII by Online Command
            try:
                import struct
                struct.pack('>f', float(value))
            except (OverflowError, struct.error) as exc:
                raise ValueError('float register value is out of float32 range') from exc
            return self._action('0907', index, value=float(value), numeric_type=1)
        raise ValueError("kind must be 'int' or 'float'")

    def start_program(self, number: int | None = None):
        """Start the configured START program (0602).

        For a numbered program, configure program_select_register in PAControl,
        only if the machine program intentionally reads that register to select
        a program. The register is written with 0906, then automatic starts.
        This is an application-level convention, NOT native numbered launching.
        """
        self._require_actions()
        if number is not None:
            if isinstance(number, bool) or not isinstance(number, int) or not 1 <= number <= 2147483647:
                raise ValueError('number must be a positive integer')
            register = getattr(self, 'program_select_register', None)
            if register is None:
                raise UnsupportedFeatureError(
                    'Native launch by program number is not documented. '
                    'Configure program_select_register only if your START program '
                    'implements a matching register-based selection.')
            self.set_register(register, number)
        return self.start_auto()
