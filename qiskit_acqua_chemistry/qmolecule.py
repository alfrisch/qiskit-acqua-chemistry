# -*- coding: utf-8 -*-

# Copyright 2018 IBM.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
# =============================================================================

import numpy
import logging
import os
import tempfile
import warnings
with warnings.catch_warnings():
    warnings.filterwarnings("ignore", category=FutureWarning)
    import h5py

logger = logging.getLogger(__name__)


class QMolecule(object):
    """Molecule data class with driver information."""

    def __init__(self, filename=None):
        if filename is None:
            fd, self._filename = tempfile.mkstemp(suffix='.hdf5')
            os.close(fd)
        else:
            self._filename = filename

        # Driver origin from which this QMolecule was created
        self._origin_driver_name       = "?"
        self._origin_driver_config     = "?"

        # Energies and orbits
        self._hf_energy                = None
        self._nuclear_repulsion_energy = None
        self._num_orbitals             = None
        self._num_alpha                = None
        self._num_beta                 = None
        self._mo_coeff                 = None
        self._orbital_energies         = None

        # Molecule geometry. xyz coords are in Bohr
        self._molecular_charge         = None
        self._multiplicity             = None
        self._num_atoms                = None
        self._atom_symbol              = None
        self._atom_xyz                 = None
        
        # 1 and 2 electron integrals in MO basis
        self._mo_onee_ints             = None
        self._mo_eri_ints              = None

        # Dipole moment integrals in MO basis
        self._x_dip_mo_ints            = None
        self._y_dip_mo_ints            = None
        self._z_dip_mo_ints            = None
        self._nuclear_dipole_moment    = None
        self._reverse_dipole_sign      = False

    @property
    def _one_body_integrals(self):
        return QMolecule.onee_to_spin(self._mo_onee_ints)

    @property
    def _two_body_integrals(self):
        mohljik = numpy.einsum('ijkl->ljik', self._mo_eri_ints)
        return QMolecule.twoe_to_spin(mohljik)

    def has_dipole_integrals(self):
        return self._x_dip_mo_ints is not None and \
               self._y_dip_mo_ints is not None and \
               self._z_dip_mo_ints is not None

    @property
    def _x_dipole_integrals(self):
        return QMolecule.onee_to_spin(self._x_dip_mo_ints)

    @property
    def _y_dipole_integrals(self):
        return QMolecule.onee_to_spin(self._y_dip_mo_ints)

    @property
    def _z_dipole_integrals(self):
        return QMolecule.onee_to_spin(self._z_dip_mo_ints)

    def Z(self, natom):
        if natom < 0 or natom >= self._num_atoms:
            raise ValueError("Atom index out of range")
        return QMolecule.symbols.index(self._atom_symbol[natom].lower().capitalize())

    @property
    def core_orbitals(self):
        count = 0
        for i in range(self._num_atoms):
            Z = self.Z(i)
            if Z > 2:  count += 1
            if Z > 10: count += 4
            if Z > 18: count += 4
            if Z > 36: count += 9
            if Z > 54: count += 9
            if Z > 86: count += 16
        return list(range(count))

    @property
    def filename(self):
        return self._filename
    
    def load(self):
        """loads info saved."""
        try:
            with h5py.File(self._filename, "r") as f:
                # Origin driver info
                data = f["origin_driver/name"][...]
                self._origin_driver_name = data[...].tobytes().decode('utf-8')
                data = f["origin_driver/config"][...]
                self._origin_driver_config = data[...].tobytes().decode('utf-8')

                # Energies
                data = f["energy/hf_energy"][...]
                self._hf_energy = float(data) if data.dtype.num != 0 else None
                data = f["energy/nuclear_repulsion_energy"][...]
                self._nuclear_repulsion_energy = float(data) if data.dtype.num != 0 else None
                
                # Orbitals
                data = f["orbitals/num_orbitals"][...]
                self._num_orbitals = int(data) if data.dtype.num != 0 else None
                data = f["orbitals/num_alpha"][...]
                self._num_alpha = int(data) if data.dtype.num != 0 else None
                data = f["orbitals/num_beta"][...]
                self._num_beta = int(data) if data.dtype.num != 0 else None
                self._mo_coeff = f["orbitals/mo_coeff"][...]
                self._orbital_energies = f["orbitals/orbital_energies"][...]

                # Molecule geometry
                data = f["geometry/molecular_charge"][...]
                self._molecular_charge = int(data) if data.dtype.num != 0 else None
                data = f["geometry/multiplicity"][...]
                self._multiplicity = int(data) if data.dtype.num != 0 else None
                data = f["geometry/num_atoms"][...]
                self._num_atoms = int(data) if data.dtype.num != 0 else None
                data = f["geometry/atom_symbol"][...]
                self._atom_symbol = [a.decode('utf8') for a in data]
                self._atom_xyz = f["geometry/atom_xyz"][...]
               
                # 1 and 2 electron integrals  
                self._mo_onee_ints = f["integrals/mo_onee_ints"][...]
                self._mo_eri_ints = f["integrals/mo_eri_ints"][...]

                # dipole integrals
                self._x_dip_mo_ints = f["dipole/x_dip_mo_ints"][...]
                self._y_dip_mo_ints = f["dipole/y_dip_mo_ints"][...]
                self._z_dip_mo_ints = f["dipole/z_dip_mo_ints"][...]
                self._nuclear_dipole_moment = f["dipole/nuclear_dipole_moment"][...]
                self._reverse_dipole_sign = f["dipole/reverse_dipole_sign"][...]

        except OSError:
            pass

    def save(self,file_name=None):
        """Saves the info from the driver."""
        file = None
        if file_name is not None:
            self.remove_file(file_name)
            file = file_name
        else:
            self.remove_file()
            file = self._filename
            
        with h5py.File(file, "w") as f:
            # Driver origin of molecule data
            g_driver = f.create_group("origin_driver")
            g_driver.create_dataset("name",
                data=(numpy.string_(self._origin_driver_name)
                      if self._origin_driver_name is not None else numpy.string_("?")))
            g_driver.create_dataset("config",
                data=(numpy.string_(self._origin_driver_config)
                      if self._origin_driver_config is not None else numpy.string_("?")))

            # Energies
            g_energy = f.create_group("energy")
            g_energy.create_dataset("hf_energy", 
                data=(self._hf_energy 
                      if self._hf_energy is not None else False))
            g_energy.create_dataset("nuclear_repulsion_energy",
                data=(self._nuclear_repulsion_energy 
                      if self._nuclear_repulsion_energy is not None else False))
        
            # Orbitals
            g_orbitals = f.create_group("orbitals")
            g_orbitals.create_dataset("num_orbitals", 
                data=(self._num_orbitals 
                      if self._num_orbitals is not None else False))
            g_orbitals.create_dataset("num_alpha", 
                data=(self._num_alpha 
                      if self._num_alpha is not None else False))
            g_orbitals.create_dataset("num_beta", 
                data=(self._num_beta 
                      if self._num_beta is not None else False))
            g_orbitals.create_dataset("mo_coeff",
                data=(self._mo_coeff
                      if self._mo_coeff is not None else False))
            g_orbitals.create_dataset("orbital_energies",
                data=(self._orbital_energies
                      if self._orbital_energies is not None else False))

            # Molecule geometry
            g_geometry = f.create_group("geometry")
            g_geometry.create_dataset("molecular_charge", 
                data=(self._molecular_charge 
                      if self._molecular_charge is not None else False))
            g_geometry.create_dataset("multiplicity", 
                data=(self._multiplicity 
                      if self._multiplicity is not None else False))
            g_geometry.create_dataset("num_atoms", 
                data=(self._num_atoms 
                      if self._num_atoms is not None else False))
            g_geometry.create_dataset("atom_symbol", 
                data=([a.encode('utf8') for a in self._atom_symbol]
                      if self._atom_symbol is not None else False))
            g_geometry.create_dataset("atom_xyz", 
                data=(self._atom_xyz 
                      if self._atom_xyz is not None else False))
            
            # 1 and 2 electron integrals  
            g_integrals = f.create_group("integrals")
            g_integrals.create_dataset("mo_onee_ints",
                data=(self._mo_onee_ints
                      if self._mo_onee_ints is not None else False))
            g_integrals.create_dataset("mo_eri_ints",
                data=(self._mo_eri_ints
                      if self._mo_eri_ints is not None else False))

            # dipole integrals
            g_dipole = f.create_group("dipole")
            g_dipole.create_dataset("x_dip_mo_ints",
                data=(self._x_dip_mo_ints
                      if self._x_dip_mo_ints is not None else False))
            g_dipole.create_dataset("y_dip_mo_ints",
                data=(self._y_dip_mo_ints
                      if self._y_dip_mo_ints is not None else False))
            g_dipole.create_dataset("z_dip_mo_ints",
                data=(self._z_dip_mo_ints
                      if self._z_dip_mo_ints is not None else False))
            g_dipole.create_dataset("nuclear_dipole_moment",
                data=(self._nuclear_dipole_moment
                      if self._nuclear_dipole_moment is not None else False))
            g_dipole.create_dataset("reverse_dipole_sign",
                data=(self._reverse_dipole_sign
                      if self._reverse_dipole_sign is not None else False))

    def remove_file(self, file_name=None):
        try:
            file = self._filename if file_name is None else file_name
            os.remove(file)
        except OSError:
            pass

    # Utility functions to convert integrals into the form expected by ACQUAChemistry stack

    @staticmethod
    def oneeints2mo(ints, moc):
        """Converts one-body integrals from AO to MO basis

        Returns one electron integrals in AO basis converted to given MO basis

        Args:
            ints: N^2 one electron integrals in AO basis
            moc: Molecular orbital coefficients
        Returns:
            integrals in MO basis
        """
        return numpy.dot(numpy.dot(numpy.transpose(moc), ints), moc)

    @staticmethod
    def twoeints2mo(ints, moc):
        """Converts two-body integrals from AO to MO basis

        Returns two electron integrals in AO basis converted to given MO basis

        Args:
            ints: N^2 two electron integrals in AO basis
            moc: Molecular orbital coefficients

        Returns:
            integrals in MO basis
        """
        dim = ints.shape[0]
        eri_mo = numpy.zeros((dim, dim, dim, dim))

        for a in range(dim):
            temp1 = numpy.einsum('i,i...->...', moc[:, a], ints)
            for b in range(dim):
                temp2 = numpy.einsum('j,j...->...', moc[:, b], temp1)
                temp3 = numpy.einsum('kc,k...->...c', moc, temp2)
                eri_mo[a, b, :, :] = numpy.einsum('ld,l...c->...cd', moc, temp3)

        return eri_mo

    @staticmethod
    def onee_to_spin(mohij, threshold=1E-12):
        """Convert one-body MO integrals to spin orbital basis

        Takes one body integrals in molecular orbital basis and returns
        integrals in spin orbitals

        Args:
            mohij: One body orbitals in molecular basis
            threshold: Threshold value for assignments
        Returns:
            One body integrals in spin orbitals
        """

        # The number of spin orbitals is twice the number of orbitals
        norbs = mohij.shape[0]
        nspin_orbs = 2*norbs

        # One electron terms
        moh1_qubit = numpy.zeros([nspin_orbs, nspin_orbs])
        for p in range(nspin_orbs):
            for q in range(nspin_orbs):
                spinp = int(p/norbs)
                spinq = int(q/norbs)
                if spinp % 2 != spinq % 2:
                    continue
                orbp = int(p % norbs)
                orbq = int(q % norbs)
                if abs(mohij[orbp, orbq]) > threshold:
                    moh1_qubit[p, q] = mohij[orbp, orbq]

        return moh1_qubit

    @staticmethod
    def twoe_to_spin(mohijkl, threshold=1E-12):
        """Convert two-body MO integrals to spin orbital basis

        Takes two body integrals in molecular orbital basis and returns
        integrals in spin orbitals

        Args:
            mohijkl: Two body orbitals in molecular basis
            threshold: Threshold value for assignments
        Returns:
            Two body integrals in spin orbitals
        """

        # The number of spin orbitals is twice the number of orbitals
        norbs = mohijkl.shape[0]
        nspin_orbs = 2*norbs

        # The spin orbitals are mapped in the following way:
        #       Orbital zero, spin up mapped to qubit 0
        #       Orbital one,  spin up mapped to qubit 1
        #       Orbital two,  spin up mapped to qubit 2
        #            .
        #            .
        #       Orbital zero, spin down mapped to qubit norbs
        #       Orbital one,  spin down mapped to qubit norbs+1
        #            .
        #            .
        #            .

        # Two electron terms
        moh2_qubit = numpy.zeros([nspin_orbs, nspin_orbs, nspin_orbs, nspin_orbs])
        for p in range(nspin_orbs):
            for q in range(nspin_orbs):
                for r in range(nspin_orbs):
                    for s in range(nspin_orbs):
                        spinp = int(p/norbs)
                        spinq = int(q/norbs)
                        spinr = int(r/norbs)
                        spins = int(s/norbs)
                        if spinp != spins:
                            continue
                        if spinq != spinr:
                            continue
                        orbp = int(p % norbs)
                        orbq = int(q % norbs)
                        orbr = int(r % norbs)
                        orbs = int(s % norbs)
                        if abs(mohijkl[orbp, orbq, orbr, orbs]) > threshold:
                            moh2_qubit[p, q, r, s] = -0.5*mohijkl[orbp, orbq, orbr, orbs]

        return moh2_qubit

    @staticmethod
    def mo_to_spin(mohij, mohijkl, threshold=1E-12):
        """Convert one and two-body MO integrals to spin orbital basis

        Takes one and two body integrals in molecular orbital basis and returns
        integrals in spin orbitals

        Args:
            mohij: One body orbitals in molecular basis
            mohijkl: Two body orbitals in molecular basis
            threshold: Threshold value for assignments

        Returns:
             One and two body integrals in spin orbitals
        """

        # One electron terms
        moh1_qubit = QMolecule.onee_to_spin(mohij, threshold)

        # Two electron terms
        moh2_qubit = QMolecule.twoe_to_spin(mohijkl, threshold)

        return moh1_qubit, moh2_qubit

    symbols = [
        '_',
        'H',  'He',
        'Li', 'Be', 'B',  'C',  'N',  'O',  'F',  'Ne',
        'Na', 'Mg', 'Al', 'Si', 'P',  'S',  'Cl', 'Ar',
        'K',  'Ca', 'Sc', 'Ti', 'V',  'Cr', 'Mn', 'Fe', 'Co', 'Ni', 'Cu', 'Zn', 'Ga', 'Ge', 'As', 'Se', 'Br', 'Kr',
        'Rb', 'Sr', 'Y',  'Zr', 'Nb', 'Mo', 'Tc', 'Ru', 'Rh', 'Pd', 'Ag', 'Cd', 'In', 'Sn', 'Sb', 'Te', 'I', 'Xe',
        'Cs', 'Ba',
        'La', 'Ce', 'Pr', 'Nd', 'Pm', 'Sm', 'Eu', 'Gd', 'Tb', 'Dy', 'Ho', 'Er', 'Tm', 'Yb', 'Lu',
        'Hf', 'Ta', 'W',  'Re', 'Os', 'Ir', 'Pt', 'Au', 'Hg', 'Tl', 'Pb', 'Bi', 'Po', 'At', 'Rn',
        'Fr', 'Ra',
        'Ac', 'Th', 'Pa', 'U',  'Np', 'Pu', 'Am', 'Cm', 'Bk', 'Cf', 'Es', 'Fm', 'Md', 'No', 'Lr',
        'Rf', 'Db', 'Sg', 'Bh', 'Hs', 'Mt', 'Ds', 'Rg', 'Cn', 'Nh', 'Fl', 'Mc', 'Lv', 'Ts', 'Og']

    BOHR = 0.52917721092  # No of Angstroms in Bohr (from 2010 CODATA)
    DEBYE = 0.393430307   # No ea0 in Debye. Use to convert our dipole moment numbers to Debye

    def log(self):
        # Originating driver name & config if set
        if len(self._origin_driver_name) > 0 and self._origin_driver_name != "?":
            logger.info("Originating driver name: {}".format(self._origin_driver_name))
            logger.info("Originating driver config:\n{}".format(self._origin_driver_config[:-1]))

        logger.info("Computed Hartree-Fock energy: {}".format(self._hf_energy))
        logger.info("Nuclear repulsion energy: {}".format(self._nuclear_repulsion_energy))
        logger.info("One and two electron Hartree-Fock energy: {}".format(self._hf_energy - self._nuclear_repulsion_energy))
        logger.info("Number of orbitals is {}".format(self._num_orbitals))
        logger.info("{} alpha and {} beta electrons".format(self._num_alpha, self._num_beta))
        logger.info("Molecule comprises {} atoms and in xyz format is ::".format(self._num_atoms))
        logger.info("  {}, {}".format(self._molecular_charge, self._multiplicity))
        if self._num_atoms is not None:
            for n in range(0, self._num_atoms):
                logger.info("  {:2s}  {}, {}, {}".format(self._atom_symbol[n],
                                                         self._atom_xyz[n][0] * QMolecule.BOHR,
                                                         self._atom_xyz[n][1] * QMolecule.BOHR,
                                                         self._atom_xyz[n][2] * QMolecule.BOHR))

        if self._nuclear_dipole_moment is not None:
            logger.info("Nuclear dipole moment: {}".format(self._nuclear_dipole_moment))
        if self._reverse_dipole_sign is not None:
            logger.info("Reversal of electronic dipole moment sign needed: {}".format(self._reverse_dipole_sign))

        if self._mo_onee_ints is not None:
            logger.info("One body MO integrals: {}".format(self._mo_onee_ints.shape))
            logger.debug(self._mo_onee_ints)

        if self._mo_eri_ints is not None:
            logger.info("Two body ERI MO integrals: {}".format(self._mo_eri_ints.shape))
            logger.debug(self._mo_eri_ints)

        if self._x_dip_mo_ints is not None:
            logger.info("x dipole MO integrals: {}".format(self._x_dip_mo_ints.shape))
            logger.debug(self._x_dip_mo_ints)
        if self._y_dip_mo_ints is not None:
            logger.info("y dipole MO integrals: {}".format(self._y_dip_mo_ints.shape))
            logger.debug(self._y_dip_mo_ints)
        if self._z_dip_mo_ints is not None:
            logger.info("z dipole MO integrals: {}".format(self._z_dip_mo_ints.shape))
            logger.debug(self._z_dip_mo_ints)

        if self._mo_coeff is not None:
            logger.info("MO coefficients: {}".format(self._mo_coeff.shape))
            logger.debug(self._mo_coeff)
        if self._orbital_energies is not None:
            logger.info("Orbital energies: {}".format(self._orbital_energies))

        logger.info("Core orbitals list {}".format(self.core_orbitals))
