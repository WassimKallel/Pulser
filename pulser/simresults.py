# Copyright 2020 Pulser Development Team
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import qutip
import numpy as np


class SimulationResults:
    """Results of a simulation run of a pulse sequence.

    Contains methods for studying the states and extracting useful information
    from them.
    """

    def __init__(self, run_output, dim, size, basis_name, meas_basis=None):
        """Initializes a new SimulationResults instance.

        Args:
            run_output (list of qutip.Qobj): List of `qutip.Qobj`corresponding
                to the states at each time step after the evolution has been
                simulated.
            dim (int): The dimension of the local space of each atom (2 or 3).
            size (int): The number of atoms in the register.
            basis_name (str): The basis indicating the addressed atoms after
                the pulse sequence ('ground-rydberg', 'digital' or 'all').

        Keyword Args:
            meas_basis (None or str): The basis in which a sampling measurement
            is desired.
        """
        self.states = run_output
        self.dim = dim
        self.size = size
        self.basis_name = basis_name
        self.meas_basis = meas_basis

    def expect(self, obs_list):
        """Calculate the expectation value of a list of observables.

        Args:
            obs_list (array-like of qutip.Qobj or array-like of np.ndarray):
                A list of observables whose expectation value will be
                calculated. If necessary, each member will be transformed into
                a qutip.Qobj instance.
        """
        if not isinstance(obs_list, (list, np.ndarray)):
            raise TypeError("`obs_list` must be a list of operators")

        qobj_list = []
        for obs in obs_list:
            if obs.shape != (self.dim**self.size, self.dim**self.size):
                raise ValueError('Incompatible shape of observable')
            # Transfrom to qutip.Qobj and take dims from state
            dim_list = [self.states[0].dims[0], self.states[0].dims[0]]
            qobj_list.append(qutip.Qobj(obs, dims=dim_list))

        return [qutip.expect(qobj, self.states) for qobj in qobj_list]

    def sample_final_state(self, meas_basis=None, N_samples=1000):
        """Returns the result of multiple measurement in a given basis.

        The enconding of the results depends on the meaurement basis. Namely:\n
        'ground-rydberg' -> 1 = |r>, 0 = |g> or |h>\n
        'digital' -> 1 = |h>, 0 = |g> or |r>\n
        The results are presented using a big-endian representation, according
        to the pre-established qubit ordering in the register. This means that
        when sampling a register with qubits ('q0','q1',...), in this order,
        the corresponding value, in binary, will be 0Bb0b1..., where b0 is
        the outcome of measuring 'q0', 'b1' of measuring 'q1' and so on.

        Keyword Args:
            meas_basis (str, default=None): 'ground-rydberg' or 'digital'. If
                left as None, uses the measurement basis defined in the
                original sequence or raises a `ValueError` if there isn't one.
            N_samples (int, default=1000): Number of samples to take.
        """
        if meas_basis is None:
            if self.meas_basis is None:
                raise ValueError(
                    "Can't accept an undefined measurement basis because the "
                    "original sequence has no measurement."
                    )
            meas_basis = self.meas_basis

        if meas_basis not in {'ground-rydberg', 'digital'}:
            raise ValueError(
                "'meas_basis' can only be 'ground-rydberg' or 'digital'."
                )

        N = self.size
        probs = np.abs(self.states[-1])**2
        if self.dim == 2:
            if meas_basis == self.basis_name:
                # State vector ordered with r first for 'ground_rydberg'
                # e.g. N=2: [rr, rg, gr, gg] -> [11, 10, 01, 00]
                # Invert the order ->  [00, 01, 10, 11] correspondence
                weights = probs if meas_basis == 'digital' else probs[::-1]
            else:
                return {'0' * N: int(N_samples)}
            weights = weights.flatten()

        elif self.dim == 3:
            if meas_basis == 'ground-rydberg':
                one_state = 0       # 1 = |r>
                ex_one = slice(1, 3)
            elif meas_basis == 'digital':
                one_state = 2       # 1 = |h>
                ex_one = slice(0, 2)

            probs = probs.reshape([3]*N)
            weights = []
            for dec_val in range(2**N):
                ind = []
                for v in np.binary_repr(dec_val, width=N):
                    if v == '0':
                        ind.append(ex_one)
                    else:
                        ind.append(one_state)
                # Eg: 'digital' basis => |1> = index 2, |0> = index 0, 1 = 0:2
                # p_11010 = sum(probs[2, 2, 0:2, 2, 0:2])
                # We sum all probabilites that correspond to measuring 11010,
                # namely hhghg, hhrhg, hhghr, hhrhr
                weights.append(np.sum(probs[tuple(ind)]))
        else:
            raise NotImplementedError(
                "Cannot sample system with single-atom state vectors of "
                "dimension > 3."
                )
        dist = np.random.multinomial(N_samples, weights)
        return {np.binary_repr(i, N): dist[i] for i in np.nonzero(dist)[0]}
